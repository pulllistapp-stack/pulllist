"""Replace S8a base card images with JP-native scans from Limitless.

LO's ask: the images we restored from Bulbapedia carry English text
because Bulbapedia only hosts EN "Celebrations" parallel scans for
the 25th Anniversary Collection — no JP-native scans on that source.

Limitless TCG (https://limitlesstcg.com/cards/jp/S8a) DOES host the
JP scans on their DigitalOcean CDN:
    https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc/S8a/
        S8a_{NUMBER}_{LIMITLESS_CODE}_JP{,_LG,_SM}.png

The Limitless code (R, RR, RRR, SR, etc.) varies per card and is
NOT the same as our JP rarity taxonomy — it's Limitless's internal
convention. We can't guess it, so we scrape each card's individual
page to extract the actual image URL from the HTML.

Coverage limits:
  - Base cards S8a-1 through S8a-29: available on Limitless ✓
  - Basic energy cards (S8a/D, /F, /G, /L, /M, /P, /R, /W): present on
    Limitless but not tracked as separate rows in our DB
  - S8a-30 Mew UR: NOT on Limitless (they cap S8a at #29)
  - S8a-P{1-25} promo pack: NOT on Limitless (no separate set)
  - S8a-G{1-15} golden box: NOT on Limitless (no separate set)

So this script covers 29/70 S8a family cards. The remaining 41 keep
their current Bulbapedia EN-Celebrations URLs — same artwork, English
text — until a per-card JP source is wired up (pokemon-card.com etc.).

Only touches cards where number_int is 1..29 on S8a. Leaves everything
else alone. Preserves image URL if the derived Limitless URL is
already what's stored (idempotent).

Usage:
    python -m scripts.restore_s8a_jp_scans_limitless --dry-run
    python -m scripts.restore_s8a_jp_scans_limitless
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


log = logging.getLogger("restore_s8a_jp_scans_limitless")


BASE = "https://limitlesstcg.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
REFERER = "https://limitlesstcg.com/"
SEM_LIMIT = 4  # be polite


# JP scan image URL pattern from Limitless card pages. Small variant
# has the CDN path we want; LG is the same URL with _LG appended,
# and we use that for image_large.
#   src="https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc/S8a/S8a_1_R_JP.png"
_JP_IMG_RE = re.compile(
    r'src="(https://limitlesstcg\.nyc3\.cdn\.digitaloceanspaces\.com'
    r'/tpc/S8a/S8a_\d+_[A-Za-z]+_JP\.png)"'
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


async def _resolve_card_image(
    client: httpx.AsyncClient, number: int
) -> tuple[str, str] | None:
    """Return (image_small_url, image_large_url) for S8a-{number}."""
    html = await _fetch(client, f"{BASE}/cards/jp/S8a/{number}")
    if not html:
        return None
    m = _JP_IMG_RE.search(html)
    if not m:
        log.warning(f"  ! S8a-{number}: no JP image match")
        return None
    small = m.group(1)
    large = small.replace(".png", "_LG.png")
    return small, large


async def run(dry_run: bool) -> None:
    await init_db()
    headers = {"User-Agent": UA, "Referer": REFERER}
    stats = {"cards_scanned": 29, "resolved": 0, "updated": 0, "unchanged": 0, "missing": 0}

    sem = asyncio.Semaphore(SEM_LIMIT)
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:

        async def resolve(num: int) -> tuple[int, tuple[str, str] | None]:
            async with sem:
                r = await _resolve_card_image(client, num)
                return num, r

        results = await asyncio.gather(*[resolve(n) for n in range(1, 30)])

    async with SessionLocal() as db:
        for num, urls in results:
            card_id = f"S8a-{num}"
            if urls is None:
                stats["missing"] += 1
                continue
            small, large = urls
            stats["resolved"] += 1

            existing = (await db.execute(
                text(
                    "SELECT image_small, image_large FROM cards "
                    "WHERE id = :id"
                ),
                {"id": card_id},
            )).first()
            if existing is None:
                stats["missing"] += 1
                continue
            if existing.image_small == small and existing.image_large == large:
                stats["unchanged"] += 1
                continue

            if dry_run:
                stats["updated"] += 1
                log.info(f"  [would] {card_id} → {small}")
                continue

            await db.execute(
                text(
                    "UPDATE cards SET image_small = :s, image_large = :l "
                    "WHERE id = :id"
                ),
                {"s": small, "l": large, "id": card_id},
            )
            stats["updated"] += 1

        if not dry_run:
            await db.commit()

    log.info("=== Limitless S8a JP-scan restore ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    log.info(
        "note: S8a-30 (Mew UR), S8a-P{1-25}, S8a-G{1-15} remain on "
        "Bulbapedia EN scans — Limitless doesn't host them"
    )
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
