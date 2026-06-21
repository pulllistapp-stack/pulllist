"""One-shot storage reclamation for the snapshot table.

Three operations, applied in order:

  B''')  Drop every cardmarket-source snapshot. We never surface
         Cardmarket pricing in the UI and the row count is ~22% of all
         snapshots — a free win.
  B')    Recompress 31-90d down from weekly to monthly. The 30d chart
         band stays usable (one point per month is still ~3 anchors
         inside a 90d window) and we lose only the visual smoothness of
         the 30d chart between the weekly markers.
  C)     VACUUM FULL on card_price_snapshots so Postgres physically
         frees the space rather than just marking tuples dead.

Run once; idempotent on re-run (just slower because there's less to do).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import SessionLocal, engine  # noqa: E402

engine.echo = False
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

log = logging.getLogger("storage_cleanup")
log.setLevel(logging.INFO)


async def _count(db, where_sql: str = "TRUE") -> int:
    q = text(f"SELECT count(*) FROM card_price_snapshots WHERE {where_sql}")
    return (await db.execute(q)).scalar() or 0


async def _table_size_mb(db) -> dict[str, float]:
    rows = (await db.execute(text(
        "SELECT pg_total_relation_size('card_price_snapshots')/1024.0/1024.0 as total_mb,"
        "       pg_relation_size('card_price_snapshots')/1024.0/1024.0 as table_mb,"
        "       (pg_total_relation_size('card_price_snapshots') - pg_relation_size('card_price_snapshots'))/1024.0/1024.0 as idx_mb"
    ))).one()
    return {"total": float(rows[0]), "table": float(rows[1]), "indexes": float(rows[2])}


async def step_drop_cardmarket(db) -> int:
    before = await _count(db, "source = 'cardmarket'")
    if before == 0:
        log.info("B''') no cardmarket snapshots to drop")
        return 0
    log.info(f"B''') dropping {before:,} cardmarket snapshots")
    res = await db.execute(text("DELETE FROM card_price_snapshots WHERE source = 'cardmarket'"))
    await db.commit()
    return res.rowcount or 0


async def step_recompress_31_90_to_monthly(db) -> int:
    """Drop snapshots in [today-90d, today-31d) that are not the latest in
    their (card, source, variant, year-month) bucket. The existing
    compress_snapshots already keeps weekly anchors in this range — we go
    one step coarser to monthly so each (card, variant) only carries 3
    rows for the 31-90d slice instead of ~9."""
    today = date.today()
    cutoff_recent = (today - timedelta(days=31)).isoformat()
    cutoff_old = (today - timedelta(days=90)).isoformat()
    log.info(f"B')  recompressing window [{cutoff_old} .. {cutoff_recent}) weekly -> monthly")

    # Same shape as the existing compress_snapshots._compress_to_weekly but
    # bucketing by year-month rather than ISO week.
    res = await db.execute(text(
        """
        DELETE FROM card_price_snapshots
        WHERE id IN (
            SELECT id FROM (
                SELECT id, row_number() OVER (
                    PARTITION BY card_id, source, variant,
                                 to_char(snapshot_date::date, 'YYYY-MM')
                    ORDER BY snapshot_date DESC
                ) AS rn
                FROM card_price_snapshots
                WHERE snapshot_date >= :cutoff_old
                  AND snapshot_date <  :cutoff_recent
            ) ranked
            WHERE rn > 1
        )
        """
    ), {"cutoff_old": cutoff_old, "cutoff_recent": cutoff_recent})
    await db.commit()
    return res.rowcount or 0


async def step_vacuum_full(db) -> None:
    """Physically reclaim the dead-tuple space the DELETEs above produced.
    VACUUM FULL takes an ACCESS EXCLUSIVE lock — fine here because nothing
    else hits this table during a maintenance window, but ON NEON the
    autovacuum reclaim happens lazily so this is genuinely needed."""
    log.info("C)   VACUUM FULL card_price_snapshots (takes a minute)…")
    # VACUUM cannot run inside a transaction block; the AsyncSession's
    # commit/begin dance gets in the way. Use the engine directly with
    # AUTOCOMMIT isolation.
    raw = await engine.connect()
    await raw.execution_options(isolation_level="AUTOCOMMIT")
    try:
        await raw.execute(text("VACUUM FULL card_price_snapshots"))
    finally:
        await raw.close()


async def run() -> None:
    async with SessionLocal() as db:
        before_total = await _count(db)
        before_size = await _table_size_mb(db)
        log.info(
            f"BEFORE: {before_total:,} rows, "
            f"{before_size['total']:.1f} MB total "
            f"({before_size['table']:.1f} table + {before_size['indexes']:.1f} indexes)"
        )

        dropped_cm = await step_drop_cardmarket(db)
        dropped_compress = await step_recompress_31_90_to_monthly(db)
        log.info(f"deleted: {dropped_cm + dropped_compress:,} rows "
                 f"({dropped_cm:,} cardmarket + {dropped_compress:,} weekly->monthly)")

    # Vacuum outside the session — it manages its own connection.
    async with SessionLocal() as db:
        await step_vacuum_full(db)

    async with SessionLocal() as db:
        after_total = await _count(db)
        after_size = await _table_size_mb(db)
        log.info(
            f"AFTER:  {after_total:,} rows, "
            f"{after_size['total']:.1f} MB total "
            f"({after_size['table']:.1f} table + {after_size['indexes']:.1f} indexes)"
        )
        reclaimed = before_size['total'] - after_size['total']
        log.info(f"reclaimed: {reclaimed:.1f} MB ({reclaimed / before_size['total'] * 100:.0f}% drop)")


if __name__ == "__main__":
    asyncio.run(run())
