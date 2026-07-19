"""Wipe eBay graded snapshots that pre-date the 5-issue scraper
hardening (2026-07-16). Those rows came from Round 2 / Round 3 runs
that had:
  * no slash-format number matcher (so "170 HP" and #116/181 leaked
    into the sm9-170 pool)
  * no `_udlo` price floor (so eBay's silent auto-relaxation on
    datacenter IPs pulled Booster Bundle / wrong-set noise into the
    sample)
  * no CGC PRISTINE 10 pattern (silently dropped $17k Pristine
    listings into `raw`)

Rounds 4 / 5 / 6 have since replaced the top ~2000 cards' data with
the clean pipeline. Every remaining pre-2026-07-16 `ebay_sold`
/ `ebay_asking` row is either
  (a) superseded — the tile already reads from a newer clean row
      and this old row just adds mass to the price chart's history
      panel; or
  (b) about a lower-value card R4-R6 didn't cover — in which case
      it's stale noise nobody wants to trust.

Deletes those rows outright. `source='ebay'` (the legacy Browse-API
active-listing snapshot) is left alone — a separate cleanup script
(`cleanup_bad_ebay_snapshots.py`) handles ratio-band violations on
that channel.

Usage:
    python -m scripts.cleanup_pre_fix_graded_snapshots            # dry-run
    python -m scripts.cleanup_pre_fix_graded_snapshots --apply
    python -m scripts.cleanup_pre_fix_graded_snapshots --before 2026-07-17 --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select

from app.database import SessionLocal, init_db
from app.models import CardPriceSnapshot


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("cleanup_pre_fix")


# Anything before this date lived on pre-fix code.
DEFAULT_CUTOFF = "2026-07-16"

TARGET_SOURCES = ("ebay_sold", "ebay_asking")


async def run(before: str, apply: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # Count first — cheap SELECT COUNT keeps dry-run fast.
        count_stmt = (
            select(
                CardPriceSnapshot.source,
                CardPriceSnapshot.grade,
                func.count(CardPriceSnapshot.id),
            )
            .where(
                CardPriceSnapshot.source.in_(TARGET_SOURCES),
                CardPriceSnapshot.snapshot_date < before,
            )
            .group_by(CardPriceSnapshot.source, CardPriceSnapshot.grade)
            .order_by(CardPriceSnapshot.source, CardPriceSnapshot.grade)
        )
        rows = (await db.execute(count_stmt)).all()
        total = sum(r[2] for r in rows)

        log.info(f"Pre-fix graded snapshots (snapshot_date < {before}):")
        for source, grade, cnt in rows:
            log.info(f"  {source:<15} {grade:<10} {cnt:>6}")
        log.info(f"  ── total: {total}")

        if not apply:
            log.info("dry-run — re-run with --apply to delete")
            return

        if total == 0:
            log.info("nothing to delete")
            return

        stmt = delete(CardPriceSnapshot).where(
            CardPriceSnapshot.source.in_(TARGET_SOURCES),
            CardPriceSnapshot.snapshot_date < before,
        )
        result = await db.execute(stmt)
        await db.commit()
        log.info(f"deleted {result.rowcount} pre-fix graded snapshot rows")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--before",
        default=DEFAULT_CUTOFF,
        help=f"delete snapshots strictly before this ISO date (default: {DEFAULT_CUTOFF})",
    )
    p.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    args = p.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run(before=args.before, apply=args.apply))


if __name__ == "__main__":
    main()
