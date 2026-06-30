"""Fill rarity='Promo' for JPP-* sets where rarity IS NULL.

The Limitless EN-equivalent picker excludes JPP-* sets (s.id NOT LIKE
'JPP-%') because Black Star Promo cards rarely have a clean 1:1 EN
equivalent in Limitless's prints table. Bulbapedia indexes JP promo
pages (XY-P_Promotional_cards etc.) but the row format uses
"001/XY-P" (no /digits) so the regex parser misses it, and the rarity
cell on those pages is usually a special symbol rather than a code.

Pragmatic answer: every JPP-* card is by definition a promo. Set
rarity='Promo' for any NULL rows so they stop tripping the frontend
"missing rarity" filter. Future work can polish to per-card variants
(Reverse Holo Promo, Holo Promo, etc.) if needed.

Usage:
    python -m scripts.backfill_jpp_promo_rarity --dry-run
    python -m scripts.backfill_jpp_promo_rarity
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jpp_promo_rarity")


async def run(dry: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        # Count first
        rows = (await db.execute(text("""
            SELECT set_id, COUNT(*) AS n
            FROM cards
            WHERE language = 'ja'
              AND set_id LIKE 'JPP-%'
              AND rarity IS NULL
            GROUP BY set_id
            ORDER BY set_id
        """))).all()
        total = sum(n for _, n in rows)
        log.info(f"NULL-rarity JPP cards: {total}")
        for sid, n in rows:
            log.info(f"  {sid:10s} {n:>5d}")

        if not total:
            log.info("Nothing to do.")
            return
        if dry:
            log.info("MODE: DRY-RUN — no writes")
            return

        # Single bulk update
        result = await db.execute(text("""
            UPDATE cards SET rarity = 'Promo'
            WHERE language = 'ja'
              AND set_id LIKE 'JPP-%'
              AND rarity IS NULL
        """))
        await db.commit()
        log.info(f"Updated {result.rowcount} JPP rows -> rarity='Promo'")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
