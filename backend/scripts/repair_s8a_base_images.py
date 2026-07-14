"""Restore correct S8a base card images from TCGCSV.

The 30 base cards took a two-step regression:

1. First S8a card-import pass overwrote their Bulbapedia scans with
   TCGCSV thumbnail URLs at 200w resolution AND a broken derived
   _1000x1000 URL for image_large.

2. A follow-up attempt to restore via Bulbapedia's card-list scraper
   pulled the wrong images entirely: the wiki page for
   /25th_Anniversary_Collection_(TCG) walks anchors in EN Celebrations
   set order (Ho-Oh, Reshiram, Kyogre, Palkia, Pikachu…) while our JP
   S8a numbers are Pikachu, Mew, Professor's Research, Ho-Oh, Lugia…
   The scraper matched by anchor position, so S8a #1 (Pikachu) ended
   up carrying the Ho-Oh Celebrations #1 image, and everything below
   shifted the same way.

This script gives up on Bulbapedia for now (a name-based JP↔EN
matcher is out of scope for the immediate fix) and reseats the 30
base rows to TCGCSV's own URLs at the correct sizes:
    image_small  → tcgplayer-cdn .../{pid}_200w.jpg
    image_large  → tcgplayer-cdn .../{pid}_400w.jpg

The pid is already stored on the row from the earlier import, so no
external fetch is needed — just derive the URLs from
``tcgplayer_product_id``. 200w/400w are the only sizes TCGCSV
actually serves (500w/800w/1000w return 403).

Idempotent — no-op after the first successful run.

Usage:
    python -m scripts.repair_s8a_base_images --dry-run
    python -m scripts.repair_s8a_base_images
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("repair_s8a_base_images")


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT id, number_int, tcgplayer_product_id, image_small, image_large
            FROM cards
            WHERE set_id = 'S8a'
              AND number_int BETWEEN 1 AND 30
            ORDER BY number_int
        """))).all()

        needs_fix = []
        for r in rows:
            pid = r.tcgplayer_product_id
            if pid is None:
                # Can't build a TCGCSV URL without a product id.
                # Skip rather than blank the image out.
                continue
            want_small = f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_200w.jpg"
            want_large = f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_400w.jpg"
            if r.image_small != want_small or r.image_large != want_large:
                needs_fix.append((r.id, want_small, want_large))

        log.info(f"S8a base rows scanned: {len(rows)}")
        log.info(f"rows needing image fix: {len(needs_fix)}")
        for cid, s, _ in needs_fix[:3]:
            log.info(f"  → {cid}: {s}")

        if dry_run:
            log.info("MODE: DRY-RUN — no writes")
            return

        for cid, small, large in needs_fix:
            await db.execute(
                text(
                    "UPDATE cards SET image_small = :s, image_large = :l "
                    "WHERE id = :id"
                ),
                {"s": small, "l": large, "id": cid},
            )
        await db.commit()
        log.info(f"fixed: {len(needs_fix)}")


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
