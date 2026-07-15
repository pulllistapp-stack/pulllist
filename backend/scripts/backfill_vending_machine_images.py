"""Replace Vending Machine placeholders with real JP scans from Bulbapedia.

JPP-VM1 / JPP-VM2 / JPP-VM3 (72 cards total) currently store the
generic ``TCG_Card_Back_Japanese.jpg`` placeholder as image_small —
users see the card back where the actual scan should be.

Bulbapedia hosts the JP scans on card wiki pages named
``/wiki/{PokemonName}_(Vending_S{1|2|3})``. Our card names follow
the same "{Name} (Vending S{N})" convention so we can build each
wiki URL by stripping the space→underscore-encoded suffix and
appending the anchor slug.

Match strategy: card ``name`` → Bulbapedia anchor. No number-order
guessing — each card individually resolves to its own wiki page.
Pulls the first ``File:`` inside ``<a class="mw-file-description">``
and strips /thumb/ to reach the full upload.

Only touches rows whose current image_small is the card back
placeholder. Rows already carrying a legitimate scan are left
alone. Idempotent.

Usage:
    python -m scripts.backfill_vending_machine_images --dry-run
    python -m scripts.backfill_vending_machine_images
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("backfill_vending_machine_images")


BASE = "https://bulbapedia.bulbagarden.net"
UA = "PullList-Catalog/1.0 (+https://pulllist.org)"
SEM_LIMIT = 4  # polite

# Card name like "Bulbasaur (Vending S1)" → base name "Bulbasaur" and
# series digit "1". Handles the "'s" possessive (Bill's PC etc.) and
# other punctuation transparently via unencoded-then-URL-encoding
# below.
_NAME_SPLIT_RE = re.compile(r"^(.*?)\s+\(Vending\s+S(\d)\)\s*$")

# Capture BOTH the File: name and the rendered src so we can filter
# out the card-back placeholder (which is itself the first image on
# every Vending card page as decoration). Old picker took the first
# src blindly, matched placeholder against placeholder, reported
# rowcount success but wrote no visible change.
_IMG_RE = re.compile(
    r'<a href="/wiki/File:([^"]+\.(?:jpg|png))"[^>]*class="mw-file-description"[^>]*>'
    r'\s*<img[^>]+src="([^"]+)"',
    re.IGNORECASE,
)

# Substrings in File: names that mark an image as decoration/UI (not
# the actual card scan). The card-back placeholder is on every
# Vending card page; kicking it out of the candidate pool lets the
# picker fall through to the real scan (BulbasaurVendingS1.jpg etc.).
_SKIP_FILE_PATTERNS = (
    "tcg_card_back",
    "project_tcg_logo",
    "setsymbol",
    "rarity_",
)
_THUMB_STRIP_RE = re.compile(
    r"/thumb/((?:[^/]+/){2}[^/]+\.(?:jpg|png))/\d+px-[^/]+$"
)

# Card-back URL currently stored on unfilled rows.
_PLACEHOLDER_URL = (
    "https://archives.bulbagarden.net/media/upload/2/2a/"
    "TCG_Card_Back_Japanese.jpg"
)


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, timeout=30, follow_redirects=True)
    except httpx.HTTPError as e:
        log.warning(f"  ! {url}: {e}")
        return None
    if r.status_code != 200:
        return None
    return r.text


async def _resolve_scan(
    client: httpx.AsyncClient, name: str, series: str
) -> str | None:
    """Return the first full-scan image URL from the card wiki page."""
    from urllib.parse import quote
    slug = f"{name.strip().replace(' ', '_')}_(Vending_S{series})"
    url = f"{BASE}/wiki/{quote(slug, safe='_()')}"
    html = await _fetch(client, url)
    if html is None:
        return None
    # Iterate all mw-file-description matches, skip decoration files,
    # take the first real card scan.
    for match in _IMG_RE.finditer(html):
        filename = match.group(1).lower()
        if any(skip in filename for skip in _SKIP_FILE_PATTERNS):
            continue
        return _THUMB_STRIP_RE.sub(r"/\1", match.group(2))
    return None


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT id, name FROM cards
            WHERE set_id IN ('JPP-VM1', 'JPP-VM2', 'JPP-VM3')
              AND image_small = :placeholder
            ORDER BY set_id, number_int
        """), {"placeholder": _PLACEHOLDER_URL})).all()

    log.info(f"Vending Machine cards with placeholder image: {len(rows)}")

    stats = {"scanned": 0, "matched": 0, "resolved": 0, "not_matched": 0, "written": 0}
    sem = asyncio.Semaphore(SEM_LIMIT)

    async def resolve(row) -> tuple[str, str | None]:
        m = _NAME_SPLIT_RE.match(row.name or "")
        if not m:
            return row.id, None
        name, series = m.group(1), m.group(2)
        async with sem:
            img = await _resolve_scan(client, name, series)
        return row.id, img

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        results = await asyncio.gather(*[resolve(r) for r in rows])

    # Per-iteration commit — the earlier batch-then-commit pattern
    # somehow returned rowcount=64 but the UPDATEs never persisted
    # (two full workflow runs both reported the same 66 placeholders,
    # neither reduced the count). Mirror the DECK phase 2 pattern
    # (backfill_deck_logos_from_ebay.py) which does open a session
    # per row and commits each time — that one is confirmed
    # working end-to-end.
    for card_id, img in results:
        stats["scanned"] += 1
        if img is None:
            stats["not_matched"] += 1
            continue
        stats["resolved"] += 1

        if dry_run:
            log.info(f"  [would] {card_id} → {img[:80]}")
            continue

        async with SessionLocal() as db:
            w = await db.execute(
                text(
                    "UPDATE cards SET image_small = :i, image_large = :i "
                    "WHERE id = :id AND image_small = :placeholder"
                ),
                {"i": img, "id": card_id, "placeholder": _PLACEHOLDER_URL},
            )
            if w.rowcount:
                stats["written"] += 1
            await db.commit()

    log.info("=== Vending Machine JP-scan restore ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
