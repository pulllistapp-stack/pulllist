"""Undo the tcgplayer-cdn image overwrite on S8a base cards.

The first S8a card-import pass clobbered image_small / image_large on
all 30 base cards (numbers 1-30, no P/G prefix) with TCGCSV thumbnail
URLs — 200w resolution vs the Bulbapedia scans they previously
carried. Additionally, the derived _1000x1000 variant used for
image_large 403s on tcgplayer-cdn, so the "large" URL is broken.

This script NULLs out those tcgplayer-cdn URLs on the base 30 rows
so the follow-up ``backfill_jp_images_bulbapedia --set S8a`` step can
re-populate them from Bulbapedia at full quality. Only touches base
cards; leaves P1-P25 (promo pack) and G1-G15 (golden box) alone
since those were freshly imported and TCGCSV thumbnails are the
best we have for them right now.

Idempotent — after the Bulbapedia backfill fires, the tcgplayer-cdn
URLs are gone, so re-running this script is a no-op.

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
        # Base cards only: id like "S8a-<int>" (no P/G prefix in the
        # numeric part). number_int between 1 and 30 covers exactly
        # the base printing.
        rows = (await db.execute(text("""
            SELECT id, number, image_small, image_large
            FROM cards
            WHERE set_id = 'S8a'
              AND number_int BETWEEN 1 AND 30
              AND (
                image_small LIKE '%tcgplayer-cdn.tcgplayer.com%'
                OR image_large LIKE '%tcgplayer-cdn.tcgplayer.com%'
              )
            ORDER BY number_int
        """))).all()
        log.info(f"S8a base cards with tcgplayer-cdn images: {len(rows)}")
        for r in rows[:5]:
            log.info(f"  {r.id}  small={r.image_small[:70] if r.image_small else '?'}")

        if dry_run:
            log.info("MODE: DRY-RUN — no writes")
            return

        r = await db.execute(text("""
            UPDATE cards
            SET image_small = NULL,
                image_large = NULL
            WHERE set_id = 'S8a'
              AND number_int BETWEEN 1 AND 30
              AND (
                image_small LIKE '%tcgplayer-cdn.tcgplayer.com%'
                OR image_large LIKE '%tcgplayer-cdn.tcgplayer.com%'
              )
        """))
        log.info(f"cleared: {r.rowcount} rows (backfill_jp_images_bulbapedia will re-fill)")
        await db.commit()


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
