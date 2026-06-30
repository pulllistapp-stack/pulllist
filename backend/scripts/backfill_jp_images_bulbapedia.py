"""Backfill image_small for vintage JP cards via Bulbapedia card-wiki pages.

ROADMAP §10.6 — pokemon-card.com / TCGdex / Bulbapedia list-pages /
pkmncards / Cardrush / yuyu-tei / Pokellector / pokemon.fandom all
turned out to be dead ends for the 1,861 vintage JP cards (PMCG /
E / PCG / VS / web). Bulbapedia *card-wiki pages* DO carry one
high-res image per card — JP-only sets (VS, Web) show the JP scan,
and EN-coupled sets (Base Expansion Pack, Mirage Forest) fall through
to the EN variant. Probe coverage: 100% across 4 sample sets.

Pattern:
- set page  /wiki/<set_slug>            → enumerate /wiki/X_(SetName_N) anchors
- card page /wiki/X_(SetName_N)         → first <a href=File:...><img src=...> match

Reuses the JP_SET_TO_BULBAPEDIA mapping from
backfill_jp_rarity_bulbapedia.py — bulbapedia slugs already vetted.

Match against DB by (set_id, language='ja', number_int) so partial
runs are safe and idempotent. Only patches rows where image_small IS
NULL — won't overwrite TCGdex/Limitless images that may already
exist for SwSh-era cards.

Usage:
    python -m scripts.backfill_jp_images_bulbapedia --dry-run
    python -m scripts.backfill_jp_images_bulbapedia --set PMCG1
    python -m scripts.backfill_jp_images_bulbapedia --limit 50
    python -m scripts.backfill_jp_images_bulbapedia  # full sweep
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db
from scripts.backfill_jp_rarity_bulbapedia import JP_SET_TO_BULBAPEDIA

log = logging.getLogger("backfill_jp_images_bulb")

BASE = "https://bulbapedia.bulbagarden.net"
SEM = 6  # polite — wiki shared infra

# Vintage sets are the documented Gap A (§10.6). We sweep all sets in
# the rarity-bulbapedia mapping by default; --only-vintage trims to
# the known-NULL-image cohort to save ~1,400 unnecessary set-page hits.
VINTAGE_SETS = [
    # PMCG = WoTC-era JP 1:1 mapping (verified 2026-06-30)
    "PMCG1", "PMCG2", "PMCG3", "PMCG4", "PMCG5", "PMCG6",
    # JP-only sets — natural JP scans on Bulbapedia
    "VS1", "web1",
    # E1 = Expedition Base Set 1:1; E2-E5 and PCG1-9 deliberately
    # omitted (EN sets cover multiple JP sets; see ROADMAP §10.6.1).
    "E1",
]

_CARD_ANCHOR_RE = re.compile(r'href="(/wiki/[^"/]+_\d+\))"[^>]*title="([^"]+)"')
# Capture both File:NAME and the rendered src — File: is unencoded and
# stable for set-token matching; src is the thumb URL we'll upgrade.
_IMG_RE = re.compile(
    r'<a href="/wiki/File:([^"]+)\.(?:jpg|png)"[^>]*class="mw-file-description"[^>]*>'
    r'\s*<img[^>]+src="([^"]+)"',
    re.IGNORECASE,
)
_NUM_FROM_HREF = re.compile(r"_(\d+)\)$")
# Extract the set token from a card-wiki href so we can prefer images
# whose filename includes that set. /wiki/Blastoise_(Base_Set_2) → "BaseSet"
_SET_FROM_HREF = re.compile(r"_\(([A-Za-z][A-Za-z_]+?)_\d+\)$")


async def _fetch(c: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await c.get(url, timeout=30)
    except httpx.HTTPError as e:
        log.warning(f"  ! {url}: {e}")
        return None
    if r.status_code != 200:
        log.warning(f"  ! {url}: HTTP {r.status_code}")
        return None
    return r.text


async def _enumerate_card_anchors(c: httpx.AsyncClient, slug: str) -> list[tuple[int, str]]:
    """Return [(card_number, href), ...] unique by number. First-seen wins."""
    html = await _fetch(c, f"{BASE}/wiki/{slug}")
    if not html:
        return []
    seen: dict[int, str] = {}
    for href, _title in _CARD_ANCHOR_RE.findall(html):
        m = _NUM_FROM_HREF.search(href)
        if not m:
            continue
        num = int(m.group(1))
        if num in seen:
            continue
        seen[num] = href
    return sorted(seen.items())


async def _extract_card_image(c: httpx.AsyncClient, href: str) -> str | None:
    """Pick the image that actually matches the set, not just the first one.

    Bulbapedia card pages list multiple variants (promo / reverse holo /
    cross-set reprints) and the first <a.mw-file-description> can be
    any of them. We pull the set token from the href and prefer images
    whose File: name contains that token (case-insensitive, underscores
    stripped — "Base_Set" → "BaseSet" matches "BlastoiseBaseSet2.jpg").
    Fallback to first when no candidate matches.
    """
    html = await _fetch(c, BASE + href)
    if not html:
        return None
    candidates = _IMG_RE.findall(html)  # [(filename, src), ...]
    if not candidates:
        return None

    set_m = _SET_FROM_HREF.search(href)
    set_token = set_m.group(1).replace("_", "").lower() if set_m else None

    pick = None
    if set_token:
        for filename, src in candidates:
            if set_token in filename.lower():
                pick = src
                break
    if not pick:
        pick = candidates[0][1]

    # Bulbapedia returns thumb URLs like
    #   .../upload/thumb/X/XX/Foo.jpg/180px-Foo.jpg
    # Strip /thumb/... to get the original full-res.
    full = re.sub(r"/thumb/((?:[^/]+/){2}[^/]+\.(?:jpg|png))/\d+px-[^/]+$", r"/\1", pick)
    return full


async def _cards_needing_image(db, set_ids: list[str]) -> dict[str, set[int]]:
    """Return {set_id: {number_int, ...}} for cards with image_small IS NULL."""
    rows = (await db.execute(text("""
        SELECT set_id, number_int
        FROM cards
        WHERE language = 'ja'
          AND set_id = ANY(:sids)
          AND image_small IS NULL
          AND number_int IS NOT NULL
    """), {"sids": set_ids})).all()
    out: dict[str, set[int]] = {}
    for sid, ni in rows:
        out.setdefault(sid, set()).add(ni)
    return out


async def run(only: str | None, dry: bool, limit: int | None, vintage_only: bool) -> None:
    await init_db()

    if only:
        target_sets = [only]
    elif vintage_only:
        target_sets = VINTAGE_SETS
    else:
        # All sets in the Bulbapedia mapping
        target_sets = list(JP_SET_TO_BULBAPEDIA.keys())

    async with SessionLocal() as db:
        needed = await _cards_needing_image(db, target_sets)
    total_needed = sum(len(s) for s in needed.values())
    log.info(f"Targets: {len(needed)} sets, {total_needed} cards needing image_small")

    if not total_needed:
        log.info("Nothing to do.")
        return

    headers = {"User-Agent": "PullList-Catalog/1.0 (+https://pulllist.org)"}
    written = 0
    skipped = 0
    no_image = 0
    sem = asyncio.Semaphore(SEM)

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as c:
        for set_idx, set_id in enumerate(target_sets, 1):
            need = needed.get(set_id, set())
            if not need:
                continue
            slug = JP_SET_TO_BULBAPEDIA.get(set_id)
            if not slug:
                log.warning(f"[{set_idx}] {set_id}: no Bulbapedia mapping")
                continue

            anchors = await _enumerate_card_anchors(c, slug)
            log.info(f"[{set_idx}/{len(target_sets)}] {set_id}: "
                     f"{len(anchors)} anchors, {len(need)} NULL-image targets")

            # Filter to just needed numbers
            todo = [(num, href) for num, href in anchors if num in need]
            if limit:
                todo = todo[:limit]

            # Fetch images concurrently within the SEM cap
            async def bounded(num, href):
                async with sem:
                    img = await _extract_card_image(c, href)
                    return num, href, img

            results = await asyncio.gather(*[bounded(n, h) for n, h in todo])

            if not dry:
                async with SessionLocal() as db:
                    for num, href, img in results:
                        if not img:
                            no_image += 1
                            continue
                        r = await db.execute(text("""
                            UPDATE cards SET image_small = :img
                            WHERE set_id = :s
                              AND language = 'ja'
                              AND number_int = :n
                              AND image_small IS NULL
                        """), {"img": img, "s": set_id, "n": num})
                        if r.rowcount:
                            written += 1
                        else:
                            skipped += 1
                    await db.commit()
            else:
                with_img = sum(1 for _, _, im in results if im)
                no_image += len(results) - with_img
                log.info(f"   would write {with_img} (dry-run)")

    log.info("\n=== Summary ===")
    log.info(f"  image_small written: {written}")
    log.info(f"  no image on wiki:    {no_image}")
    log.info(f"  skipped (raced/no-op): {skipped}")
    if dry:
        log.info("  MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", dest="only", help="One JP set id (e.g. PMCG1)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, help="Cap cards per set (smoke test)")
    p.add_argument(
        "--vintage-only",
        action="store_true",
        default=True,
        help="Restrict to PMCG/VS/web/E/PCG (default — modern sets already have images via TCGdex/Limitless)",
    )
    p.add_argument(
        "--all-sets",
        dest="vintage_only",
        action="store_false",
        help="Sweep ALL sets in the Bulbapedia mapping, not just vintage",
    )
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.only, args.dry_run, args.limit, args.vintage_only))


if __name__ == "__main__":
    main()
