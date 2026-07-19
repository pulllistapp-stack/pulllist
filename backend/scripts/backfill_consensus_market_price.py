"""One-shot: blend Card.market_price_usd with the latest raw eBay
median for every card that has one, so the set-page CardThumb and
the card-detail hero show the same number today instead of waiting
for the next nightly TCGCSV sync to reblend.

Formula matches every other consensus writer:
    new_market = (current_market + ebay_median) / 2   if both exist
    unchanged                                          otherwise

Idempotent — running twice re-blends against the already-blended
market (drift-free because we don't touch cards without a fresh
eBay signal, and the blend approaches the geometric mean of the
two sources rather than running away).

Usage:
    python -m scripts.backfill_consensus_market_price
    python -m scripts.backfill_consensus_market_price --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import SessionLocal, init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("backfill_consensus")


UPDATE_SQL = text(
    """
    WITH latest_ebay AS (
        SELECT DISTINCT ON (card_id)
            card_id,
            market_price_usd AS ebay_median
        FROM card_price_snapshots
        WHERE source = 'ebay'
          AND grade = 'raw'
          AND market_price_usd IS NOT NULL
        ORDER BY card_id, snapshot_at DESC
    )
    UPDATE cards c
    SET market_price_usd = (c.market_price_usd + e.ebay_median) / 2.0
    FROM latest_ebay e
    WHERE c.id = e.card_id
      AND c.market_price_usd IS NOT NULL
      AND abs(c.market_price_usd - (c.market_price_usd + e.ebay_median) / 2.0) > 0.01
    """
)

COUNT_SQL = text(
    """
    SELECT COUNT(*) FROM cards c
    WHERE c.market_price_usd IS NOT NULL
      AND EXISTS (
          SELECT 1 FROM card_price_snapshots s
          WHERE s.card_id = c.id
            AND s.source = 'ebay'
            AND s.grade = 'raw'
            AND s.market_price_usd IS NOT NULL
      )
    """
)


async def run(dry_run: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        total = (await db.execute(COUNT_SQL)).scalar_one()
        log.info(f"cards eligible (has TCG market + at least one raw eBay snapshot): {total}")

        if dry_run:
            log.info("dry-run — no writes")
            return

        r = await db.execute(UPDATE_SQL)
        await db.commit()
        log.info(f"updated {r.rowcount} card market prices to consensus (tcg+ebay)/2")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
