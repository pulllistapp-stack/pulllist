"""Daily portfolio valuation snapshot.

For every user with at least one card in their collection, write a single
row to `portfolio_snapshots` capturing today's total estimated value,
unique card count, total qty, and number of distinct sets touched.

Runs daily AFTER the eBay + TCGplayer crons so Card.market_price_usd is
fresh. Idempotent — re-running on the same day is a no-op.

Usage:
    python -m scripts.snapshot_portfolios                  # today
    python -m scripts.snapshot_portfolios --date 2026-06-13 # backfill
    python -m scripts.snapshot_portfolios --dry-run        # don't write
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, init_db
from app.models import Card, CollectionItem, PortfolioSnapshot, User

log = logging.getLogger("snapshot_portfolios")


def _conflict_insert(dialect_name: str):
    if dialect_name == "postgresql":
        return pg_insert(PortfolioSnapshot)
    return sqlite_insert(PortfolioSnapshot)


async def compute_user_value(
    db: AsyncSession, user_id: str
) -> tuple[float, int, int, int]:
    """Return (estimated_value_usd, unique_cards, total_qty, sets_touched)."""
    stmt = (
        select(
            func.count(func.distinct(CollectionItem.card_id)).label("unique_cards"),
            func.coalesce(func.sum(CollectionItem.qty), 0).label("total_qty"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Card.market_price_usd.is_not(None),
                            CollectionItem.qty * Card.market_price_usd,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("value"),
            func.count(func.distinct(Card.set_id)).label("sets_touched"),
        )
        .join(Card, CollectionItem.card_id == Card.id)
        .where(CollectionItem.user_id == user_id)
    )
    row = (await db.execute(stmt)).one()
    return (
        round(float(row.value or 0), 2),
        int(row.unique_cards or 0),
        int(row.total_qty or 0),
        int(row.sets_touched or 0),
    )


async def run(snapshot_date: str, dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # Only users that have at least one CollectionItem are worth snapshotting.
        user_ids = (
            await db.execute(
                select(CollectionItem.user_id).distinct()
            )
        ).scalars().all()

    if not user_ids:
        log.warning("No users with collections — nothing to snapshot.")
        return

    log.info(
        "Snapshotting portfolios for %d user(s) (%s)…",
        len(user_ids),
        snapshot_date,
    )

    rows: list[dict] = []
    async with SessionLocal() as db:
        for uid in user_ids:
            value, unique_cards, total_qty, sets_touched = await compute_user_value(
                db, uid
            )
            rows.append(
                {
                    "user_id": uid,
                    "snapshot_date": snapshot_date,
                    "estimated_value_usd": value,
                    "unique_cards": unique_cards,
                    "total_qty": total_qty,
                    "sets_touched": sets_touched,
                    "snapshot_at": datetime.utcnow(),
                }
            )
            log.info(
                "  %s: $%.2f · %d unique · %d total · %d sets",
                uid[:8],
                value,
                unique_cards,
                total_qty,
                sets_touched,
            )

        if dry_run:
            log.info("Dry run — %d rows would be written.", len(rows))
            return

        dialect_name = db.bind.dialect.name
        stmt = _conflict_insert(dialect_name).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["user_id", "snapshot_date"]
        )
        result = await db.execute(stmt)
        await db.commit()
        log.info("Wrote %d portfolio snapshots.", result.rowcount or 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        dest="snapshot_date",
        help="YYYY-MM-DD (defaults to today UTC).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Compute but don't write."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Debug logs."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    snapshot_date = args.snapshot_date or date.today().isoformat()
    asyncio.run(run(snapshot_date, args.dry_run))


if __name__ == "__main__":
    main()
