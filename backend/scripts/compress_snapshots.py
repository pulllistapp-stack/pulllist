"""Tiered snapshot retention.

Keeps the chart UX intact while reclaiming Postgres storage that would
otherwise pin us against Neon's free tier:

    last 7 days   -> daily granularity (no change)
    8-90 days     -> 1 snapshot per (card, source, variant, ISO week)
    91-365 days   -> 1 snapshot per (card, source, variant, year-month)
    >365 days     -> deleted

"Keep" means we keep the LATEST snapshot inside each retention bucket
(month-end is the most useful representative for 1Y-view aggregators).
Older redundant rows in that bucket are dropped.

Usage:
    python -m scripts.compress_snapshots --dry-run     # count only, no writes
    python -m scripts.compress_snapshots               # apply

Idempotent. Safe to run weekly via cron. No backups taken — sized
retention WAL covers a few hours of rollback if something goes sideways.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import delete, select, text

from app.database import SessionLocal, init_db
from app.models import CardPriceSnapshot

log = logging.getLogger("retention")


async def _count(db, where_sql: str) -> int:
    q = text(
        "SELECT COUNT(*) FROM card_price_snapshots WHERE " + where_sql
    )
    return (await db.execute(q)).scalar() or 0


async def _compress_to_weekly(db, cutoff_recent: str, cutoff_old: str, dry: bool) -> int:
    """For snapshots in [cutoff_old, cutoff_recent), keep only one per ISO week.

    The kept row is the one with the highest snapshot_date inside its
    (card_id, source, variant, ISO-week) bucket; the rest are deleted.
    """
    # All ids in window that are NOT the latest in their ISO-week bucket.
    find_sql = text(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY card_id, source, variant,
                                 to_char(snapshot_date::date, 'IYYY-IW')
                    ORDER BY snapshot_date DESC
                ) AS rn
            FROM card_price_snapshots
            WHERE snapshot_date >= :cutoff_old
              AND snapshot_date <  :cutoff_recent
        )
        SELECT id FROM ranked WHERE rn > 1
        """
    )
    ids = [
        r[0]
        for r in (
            await db.execute(
                find_sql, {"cutoff_old": cutoff_old, "cutoff_recent": cutoff_recent}
            )
        ).all()
    ]
    log.info(f"  weekly-compress window [{cutoff_old}..{cutoff_recent}): "
             f"{len(ids):,} redundant rows")
    if dry or not ids:
        return len(ids)
    deleted = await _chunked_delete(db, ids, chunk=2_000)
    return deleted


async def _compress_to_monthly(db, cutoff_recent: str, cutoff_old: str, dry: bool) -> int:
    """For snapshots in [cutoff_old, cutoff_recent), keep only one per year-month."""
    find_sql = text(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY card_id, source, variant,
                                 substring(snapshot_date for 7)
                    ORDER BY snapshot_date DESC
                ) AS rn
            FROM card_price_snapshots
            WHERE snapshot_date >= :cutoff_old
              AND snapshot_date <  :cutoff_recent
        )
        SELECT id FROM ranked WHERE rn > 1
        """
    )
    ids = [
        r[0]
        for r in (
            await db.execute(
                find_sql, {"cutoff_old": cutoff_old, "cutoff_recent": cutoff_recent}
            )
        ).all()
    ]
    log.info(f"  monthly-compress window [{cutoff_old}..{cutoff_recent}): "
             f"{len(ids):,} redundant rows")
    if dry or not ids:
        return len(ids)
    deleted = await _chunked_delete(db, ids, chunk=2_000)
    return deleted


async def _drop_older_than(db, cutoff: str, dry: bool) -> int:
    """Snapshots older than `cutoff` are gone for good."""
    n = (await db.execute(
        text("SELECT COUNT(*) FROM card_price_snapshots WHERE snapshot_date < :c"),
        {"c": cutoff},
    )).scalar() or 0
    log.info(f"  drop window  [<{cutoff}): {n:,} rows")
    if dry or n == 0:
        return n
    await db.execute(
        delete(CardPriceSnapshot).where(CardPriceSnapshot.snapshot_date < cutoff)
    )
    await db.commit()
    return n


async def _chunked_delete(db, ids: list[int], chunk: int) -> int:
    """DELETE WHERE id IN (...) in chunks so the txn stays small."""
    total = 0
    for i in range(0, len(ids), chunk):
        batch = ids[i:i + chunk]
        await db.execute(
            delete(CardPriceSnapshot).where(CardPriceSnapshot.id.in_(batch))
        )
        await db.commit()
        total += len(batch)
        if i % (chunk * 10) == 0:
            log.info(f"    deleted {total:,}/{len(ids):,}")
    return total


async def run(dry: bool) -> None:
    today = date.today()
    cutoff_7d = (today - timedelta(days=7)).isoformat()
    cutoff_90d = (today - timedelta(days=90)).isoformat()
    cutoff_365d = (today - timedelta(days=365)).isoformat()

    log.info(f"Retention cutoffs (today={today}): "
             f"7d={cutoff_7d}, 90d={cutoff_90d}, 365d={cutoff_365d}")

    async with SessionLocal() as db:
        total_before = (
            await db.execute(text("SELECT COUNT(*) FROM card_price_snapshots"))
        ).scalar() or 0
        log.info(f"Total snapshots before: {total_before:,}")

        # Order matters: drop oldest first, then compress middle tier
        # (smaller working set), then compress recent tier (smallest set).
        d_old = await _drop_older_than(db, cutoff_365d, dry)
        d_mon = await _compress_to_monthly(db, cutoff_90d, cutoff_365d, dry)
        d_week = await _compress_to_weekly(db, cutoff_7d, cutoff_90d, dry)

        total_after = (
            await db.execute(text("SELECT COUNT(*) FROM card_price_snapshots"))
        ).scalar() or 0

    log.info("\n=== Retention summary ===")
    log.info(f"  Dropped (>1y)        : {d_old:,}")
    log.info(f"  Compressed to monthly: {d_mon:,}")
    log.info(f"  Compressed to weekly : {d_week:,}")
    log.info(f"  Total removed        : {d_old + d_mon + d_week:,}")
    log.info(f"  Snapshots before     : {total_before:,}")
    log.info(f"  Snapshots after      : {total_after:,}")
    if dry:
        log.info("  MODE                 : DRY RUN (no changes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows that would be touched; do not delete.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    # Quiet down SQLAlchemy/asyncpg engine noise.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    asyncio.run(_bootstrap_and_run(args.dry_run))


async def _bootstrap_and_run(dry: bool) -> None:
    await init_db()
    await run(dry)


if __name__ == "__main__":
    main()
