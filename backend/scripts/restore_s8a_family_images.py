"""HD-restore images for the S8a 25th Anniversary family.

The general Bulbapedia backfill script matches anchors by position on
the set's wiki page, which broke for S8a because Bulbapedia's
25th Anniversary Collection page ALSO enumerates the EN parallel
"Celebrations" set anchors, and Celebrations comes first in the HTML —
so anchor #1 was Ho-Oh (Celebrations #1) not Pikachu (S8a #1).

This targeted script pins each of the three S8a family sub-collections
to its actual Bulbapedia URL slug and only harvests anchors whose href
contains that exact slug + a trailing "_N)" suffix:

    base    S8a-N       ← href like Pikachu_(25th_Anniversary_Collection_1)
    promo   S8a-P{N}    ← href like Charizard_(Promo_Card_Pack_25th_Anniversary_Edition_1)
    golden  S8a-G{N}    ← href like Bede_(25th_Anniversary_Golden_Box_13)

For each matched anchor the card wiki page is fetched, the largest
non-thumbnail image URL is picked (Bulbapedia serves .../thumb/…/N-…
resized proxies — stripping /thumb/…/Npx-… gives the original full
scan), and the corresponding PullList card row's image_small +
image_large get set to that URL.

number_int scheme (mirrors the merge-time convention):
    base   1..30
    promo  101..125   (offset 100)
    golden 201..215   (offset 200)

Only touches image_small / image_large. Preserves everything else.
Idempotent — subsequent runs only re-write rows where the derived
URL differs, so the second run is a no-op.

Usage:
    python -m scripts.restore_s8a_family_images --dry-run
    python -m scripts.restore_s8a_family_images
    python -m scripts.restore_s8a_family_images --subset base
    python -m scripts.restore_s8a_family_images --subset promo,golden
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


log = logging.getLogger("restore_s8a_family_images")


BASE = "https://bulbapedia.bulbagarden.net"
UA = "PullList-Catalog/1.0 (+https://pulllist.org)"
SEM_LIMIT = 6  # polite — Bulbapedia is shared infrastructure


# Per-subset config. slug = wiki page for the set; anchor_slug is the
# _(...)_N) fragment that identifies cards belonging to this set (used
# to disambiguate from cross-linked anchors like the EN Celebrations
# reprints on the same page). id_prefix / number_prefix / int_offset
# are the merge-time namespacing rules; see docstring.
_SUBSETS: dict[str, dict] = {
    "base": {
        "slug": "25th_Anniversary_Collection_(TCG)",
        "anchor_slug": "25th_Anniversary_Collection",
        "number_prefix": "",
        "int_offset": 0,
        "id_range": (1, 30),
    },
    "promo": {
        "slug": "Promo_Card_Pack_25th_Anniversary_Edition_(TCG)",
        "anchor_slug": "Promo_Card_Pack_25th_Anniversary_Edition",
        "number_prefix": "P",
        "int_offset": 100,
        "id_range": (101, 125),
    },
    "golden": {
        "slug": "25th_Anniversary_Golden_Box_(TCG)",
        "anchor_slug": "25th_Anniversary_Golden_Box",
        "number_prefix": "G",
        "int_offset": 200,
        "id_range": (201, 215),
    },
}


# Image-picker helpers. Bulbapedia card pages embed 1..N variant images
# under <a href="/wiki/File:…" class="mw-file-description"><img …>. We
# want the FULL-scan URL (Bulbapedia's /upload/X/XX/Foo.jpg), not the
# resized proxy at /upload/thumb/X/XX/Foo.jpg/180px-Foo.jpg.
_IMG_RE = re.compile(
    r'<a href="/wiki/File:([^"]+)\.(?:jpg|png)"[^>]*class="mw-file-description"[^>]*>'
    r'\s*<img[^>]+src="([^"]+)"',
    re.IGNORECASE,
)
_THUMB_STRIP_RE = re.compile(
    r"/thumb/((?:[^/]+/){2}[^/]+\.(?:jpg|png))/\d+px-[^/]+$"
)

# Card-name extract: /wiki/Pikachu_V_(25th_Anniversary_Golden_Box_1) →
# "Pikachu_V". Bulbapedia URL-encodes special characters (' → %27),
# leave them alone for straight substring comparison.
_CARD_NAME_FROM_HREF = re.compile(r"/wiki/([^/]+?)_\([^)]+\)$")

# Filenames that are page-decoration or mechanic-mark icons, not
# actual card scans. Bulbapedia embeds these inside the same
# <a class="mw-file-description"> shell so the picker can't tell them
# apart without a blacklist.
_GENERIC_ICON_RE = re.compile(
    r"^(Pok[e\xe9%C3%A9]+?mon_[A-Z0-9\-]{1,6}|"
    r"Project_TCG_logo|"
    r"Rarity_|"
    r"SetSymbol|"
    r"Team_Rocket_|"
    r"MSP)",
    re.IGNORECASE,
)


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, timeout=30)
    except httpx.HTTPError as e:
        log.warning(f"  ! {url}: {e}")
        return None
    if r.status_code != 200:
        log.warning(f"  ! {url}: HTTP {r.status_code}")
        return None
    return r.text


def _extract_anchors(html: str, anchor_slug: str) -> dict[int, str]:
    """Return {card_number: href} for anchors matching this subset."""
    pat = re.compile(
        rf'href="(/wiki/[^"/]+_\({re.escape(anchor_slug)}_(\d+)\))"'
    )
    out: dict[int, str] = {}
    for href, num_s in pat.findall(html):
        num = int(num_s)
        if num not in out:  # first-seen wins
            out[num] = href
    return out


# Rarities that identify a secret/hyper printing. On a Bulbapedia card
# page these variants usually sit LATER in the image list (base scan
# first, secret rare scan after) or carry a higher trailing set-index
# in the filename ("MewCelebrations25.jpg" for the UR Mew vs
# "MewCelebrations11.jpg" for the base holo). So for these rarities we
# invert the picker's preference: prefer the LAST card-name match with
# the HIGHEST trailing integer instead of the first.
_SECRET_RARITIES = {"SR", "SAR", "HR", "UR", "SSR"}

# Trailing-integer extractor from a Bulbapedia filename stub. Used to
# rank same-Pokemon variants when the card is a secret rare — the
# higher trailing number is virtually always the higher-rarity print
# on Bulbapedia's card wiki pages.
_TRAILING_INT_RE = re.compile(r"(\d+)$")


def _trailing_int(filename: str) -> int:
    m = _TRAILING_INT_RE.search(filename)
    return int(m.group(1)) if m else -1


async def _extract_card_image(
    client: httpx.AsyncClient, href: str, anchor_slug: str,
    rarity: str | None = None,
) -> str | None:
    """Fetch card wiki page, return the best full-scan URL.

    Bulbapedia card pages list multiple images inside
    <a class="mw-file-description">: mechanic icons (Pokemon_V.png,
    Pokemon_GX.png), the TCG project logo, then the actual card
    scans (often multiple variants — the JP-set scan, the EN parallel
    Celebrations scan, cross-set reprints).

    Selection priority:
      1. filter out generic mechanic/project icons via blacklist
      2. among the rest, prefer files whose name matches the anchor's
         set token (e.g. "25thanniversarygoldenbox")
      3. otherwise prefer files whose name contains the Pokemon's
         card-name portion of the href ("PikachuV", "Mew", …) so a
         cross-Pokemon match can't leak in
      4. finally, first non-generic candidate as a last resort
    Never falls back to a blacklisted generic — better to return None
    and stick with the TCGCSV fallback than serve a Pokemon-V icon
    where a card scan should be.
    """
    html = await _fetch(client, BASE + href)
    if not html:
        return None
    candidates = _IMG_RE.findall(html)
    if not candidates:
        return None

    # Drop generic mechanic/logo images up front — no legitimate card
    # scan would ever be named "Pokemon_V.png" or "Project_TCG_logo".
    non_generic = [
        (f, s) for f, s in candidates if not _GENERIC_ICON_RE.match(f)
    ]
    if not non_generic:
        return None  # only icons on the page — nothing usable

    token = anchor_slug.replace("_", "").lower()
    name_m = _CARD_NAME_FROM_HREF.search(href)
    card_name = name_m.group(1) if name_m else ""
    card_name_stripped = card_name.replace("_", "").lower()

    # Tier 1: filename contains the set-specific token
    for filename, src in non_generic:
        if token in filename.lower():
            return _THUMB_STRIP_RE.sub(r"/\1", src)

    # Tier 2: filename contains the card-name portion (guards against
    # e.g. serving MewCrownZenithGG10.jpg for Mew #30 when the wiki
    # cross-links other Mew cards).
    if card_name_stripped:
        name_matches = [
            (f, s) for f, s in non_generic
            if card_name_stripped in f.lower()
        ]
        if name_matches:
            # For secret/hyper rare cards, prefer the variant with the
            # HIGHEST trailing integer — Bulbapedia orders the base
            # holo first and the secret print later on the same card
            # page, and encodes the print position in the filename
            # (MewCelebrations11 = base, MewCelebrations25 = UR).
            # For everything else, the first name match is correct.
            if rarity and rarity.upper() in _SECRET_RARITIES:
                pick = max(name_matches, key=lambda fs: _trailing_int(fs[0]))
                return _THUMB_STRIP_RE.sub(r"/\1", pick[1])
            return _THUMB_STRIP_RE.sub(r"/\1", name_matches[0][1])

    # Tier 3: first surviving non-generic candidate. Better than
    # nothing when Bulbapedia only hosts a parallel-set image.
    return _THUMB_STRIP_RE.sub(r"/\1", non_generic[0][1])


async def restore_subset(
    client: httpx.AsyncClient,
    label: str,
    cfg: dict,
    dry_run: bool,
) -> dict[str, int]:
    stats = {"anchors_found": 0, "images_resolved": 0, "updated": 0, "unchanged": 0, "missing": 0}

    html = await _fetch(client, f"{BASE}/wiki/{cfg['slug']}")
    if not html:
        log.error(f"[{label}] could not fetch set page")
        return stats

    anchors = _extract_anchors(html, cfg["anchor_slug"])
    stats["anchors_found"] = len(anchors)
    log.info(f"[{label}] anchors matching '{cfg['anchor_slug']}_N': {len(anchors)}")

    # Preload the current rarity per S8a-{N|PN|GN} so the picker can
    # choose the secret-rare variant when needed (Mew UR should get
    # MewCelebrations25 not MewCelebrations11).
    prefix = cfg["number_prefix"]
    ids_to_rarity: dict[int, str | None] = {}
    async with SessionLocal() as db:
        rows = (await db.execute(
            text("""
                SELECT number_int, rarity FROM cards
                WHERE set_id = 'S8a' AND number_int BETWEEN :lo AND :hi
            """),
            {"lo": cfg["id_range"][0], "hi": cfg["id_range"][1]},
        )).all()
        for r in rows:
            ids_to_rarity[r.number_int] = r.rarity

    sem = asyncio.Semaphore(SEM_LIMIT)

    async def resolve(num: int, href: str) -> tuple[int, str | None]:
        rarity = ids_to_rarity.get(cfg["int_offset"] + num)
        async with sem:
            img = await _extract_card_image(
                client, href, cfg["anchor_slug"], rarity=rarity,
            )
            return num, img

    results = await asyncio.gather(*[resolve(n, h) for n, h in anchors.items()])

    lo, hi = cfg["id_range"]
    prefix = cfg["number_prefix"]

    async with SessionLocal() as db:
        for base_num, img in results:
            if img is None:
                stats["missing"] += 1
                continue
            stats["images_resolved"] += 1

            # Numbered "N" (base) or "P{N}" / "G{N}" (sub-sets); id
            # follows the {set}-{number} convention.
            display_number = f"{prefix}{base_num}"
            card_id = f"S8a-{display_number}"
            num_int = cfg["int_offset"] + base_num

            if not (lo <= num_int <= hi):
                log.warning(
                    f"[{label}] anchor N={base_num} maps to int={num_int} "
                    f"outside {lo}-{hi} — skipping"
                )
                continue

            existing = (await db.execute(
                text(
                    "SELECT image_small, image_large FROM cards "
                    "WHERE id = :id"
                ),
                {"id": card_id},
            )).first()
            if existing is None:
                stats["missing"] += 1
                log.debug(f"[{label}] card {card_id} not in DB")
                continue

            if existing.image_small == img and existing.image_large == img:
                stats["unchanged"] += 1
                continue

            if dry_run:
                stats["updated"] += 1
                log.info(f"  [would] {card_id} → {img[:80]}")
                continue

            await db.execute(
                text(
                    "UPDATE cards SET image_small = :i, image_large = :i "
                    "WHERE id = :id"
                ),
                {"i": img, "id": card_id},
            )
            stats["updated"] += 1

        if not dry_run:
            await db.commit()

    return stats


async def run(subsets: list[str], dry_run: bool) -> None:
    await init_db()

    headers = {"User-Agent": UA}
    grand: dict[str, int] = {}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for label in subsets:
            cfg = _SUBSETS.get(label)
            if cfg is None:
                log.warning(f"unknown subset {label!r}, skipping")
                continue
            log.info(f"=== restore {label} ===")
            stats = await restore_subset(client, label, cfg, dry_run)
            for k, v in stats.items():
                log.info(f"  {k}: {v}")
                grand[k] = grand.get(k, 0) + v

    log.info("=== grand total ===")
    for k, v in grand.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--subset",
        default="base,promo,golden",
        help="Comma list of base|promo|golden (default: all three).",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    subsets = [s.strip() for s in args.subset.split(",") if s.strip()]
    asyncio.run(run(subsets, args.dry_run))


if __name__ == "__main__":
    main()
