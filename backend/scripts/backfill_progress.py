"""Quick one-shot status check for the long-running TCG backfill.

Use:
    python -m scripts.backfill_progress

Reports:
  - How many cards qualified for the backfill (target).
  - How many have a resolved TCGplayer product_id so far.
  - How many monthly history snapshot rows have been written.
  - Recent activity in the last N minutes (default 30) to confirm the
    background script is still alive.

No writes — safe to run whenever.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot


async def main(window_min: int) -> None:
    logging.disable(logging.CRITICAL)
    await init_db()

    async with SessionLocal() as db:
        target = (
            await db.execute(
                select(func.count(Card.id))
                .where(Card.tcgplayer_url.is_not(None))
                .where(Card.language == "en")
                .where(Card.market_price_usd >= 5)
            )
        ).scalar() or 0
        resolved = (
            await db.execute(
                select(func.count(Card.id)).where(Card.tcgplayer_product_id.is_not(None))
            )
        ).scalar() or 0
        total_snaps = (
            await db.execute(
                select(func.count(CardPriceSnapshot.id)).where(
                    CardPriceSnapshot.source == "tcgplayer"
                )
            )
        ).scalar() or 0
        since = datetime.utcnow() - timedelta(minutes=window_min)
        recent_snaps = (
            await db.execute(
                select(func.count(CardPriceSnapshot.id)).where(
                    and_(
                        CardPriceSnapshot.source == "tcgplayer",
                        CardPriceSnapshot.snapshot_at >= since,
                    )
                )
            )
        ).scalar() or 0

    pct = (resolved / target * 100) if target else 0
    # Throughput estimate: each completed card writes ~12 monthly rows.
    # snaps_per_min / 12 ≈ cards processed per minute.
    snaps_per_min = recent_snaps / max(window_min, 1)
    cards_per_min = snaps_per_min / 12
    remaining = max(target - resolved, 0)
    eta_hr = (remaining / cards_per_min / 60) if cards_per_min > 0 else 0

    print(f"\n  TARGET            : {target:,} cards (>=$5 with TCGplayer URL)")
    print(f"  product_id done   : {resolved:,}  ({pct:.1f}%)")
    print(f"  tcg snaps in DB   : {total_snaps:,}")
    print(f"  written last {window_min}m   : {recent_snaps:,}  ({snaps_per_min:.0f}/min)")
    if recent_snaps == 0:
        print(f"  STATUS            : no activity in window - backfill may be stalled or finished")
    else:
        print(f"  ETA (rough)       : ~{eta_hr:.1f}h remaining ({cards_per_min:.0f} cards/min)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-min", type=int, default=30,
                        help="Window for 'recent activity' check (default 30 min)")
    args = parser.parse_args()
    asyncio.run(main(args.window_min))
