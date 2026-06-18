"""Quick one-shot status check for the long-running TCG backfill.

Use:
    python -m scripts.backfill_progress

Reports:
  - How many cards qualified for the backfill (target).
  - How many have a resolved TCGplayer product_id so far.
  - How many monthly history snapshot rows have been written.
  - Recent activity in the last N minutes (default 30) to confirm the
    background script is still alive.
  - In weekly mode, reads backfill_weekly.log for accurate per-card
    progress (the product_id metric saturates from the monthly pass and
    cannot represent weekly work).

No writes - safe to run whenever.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import and_, func, select

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot

_LOG_CANDIDATES = ("backfill_weekly.log", "backfill_v5.log")
_PROGRESS_PATTERN = re.compile(r"\[(\d+)/(\d+)\]")


def _read_progress_from_log() -> tuple[int, int, str] | None:
    """Scan the most recent backfill log file for the latest [N/total] line.

    Returns (current, total, source_filename) or None if no progress line
    is parseable. Reads only the tail (last 16KB) so it stays cheap even
    when the log grows large.
    """
    here = Path(__file__).resolve().parent.parent  # backend/
    for name in _LOG_CANDIDATES:
        path = here / name
        if not path.exists():
            continue
        # Progress lines emit every 50 cards (~100s apart), but the log
        # is interleaved with verbose HTTP/SQL noise that can spam 500+
        # lines between progress markers. Read a generous 2MB tail to
        # ensure at least one [N/total] survives the haystack.
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 2_000_000))
                tail = f.read().decode("utf-8", errors="ignore")
        except OSError:
            continue
        matches = _PROGRESS_PATTERN.findall(tail)
        if matches:
            cur, tot = matches[-1]
            return int(cur), int(tot), name
    return None


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
        # snapshot_at is TIMESTAMP WITHOUT TIME ZONE in the DB - strip tz
        # info after computing UTC-now so we don't trip asyncpg's strict
        # parameter binding.
        since = (datetime.now(timezone.utc) - timedelta(minutes=window_min)).replace(tzinfo=None)
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
    snaps_per_min = recent_snaps / max(window_min, 1)
    # Once product_id resolution saturates (>=95% of target), the active
    # workload is the weekly densification pass, not the original monthly
    # pass. They have different snaps-per-card averages and need different
    # ETA math.
    weekly_mode = pct >= 95 and target > 0
    snaps_per_card = 40 if weekly_mode else 12
    cards_per_min = snaps_per_min / snaps_per_card

    # In weekly mode the product_id metric is pinned at ~99% from the
    # earlier monthly pass and can't tell us how far weekly has gotten -
    # the script's own [N/total] log line is the ground truth.
    log_progress = _read_progress_from_log() if weekly_mode else None

    if log_progress is not None:
        cur, tot, log_name = log_progress
        weekly_pct = (cur / tot * 100) if tot else 0
        remaining = max(tot - cur, 0)
    else:
        weekly_pct = None
        remaining = max(target - resolved, 0) if not weekly_mode else target

    eta_min = (remaining / cards_per_min) if cards_per_min > 0 else 0

    print(f"\n  TARGET            : {target:,} cards (>=$5 with TCGplayer URL)")
    print(f"  product_id done   : {resolved:,}  ({pct:.1f}%)")
    print(f"  tcg snaps in DB   : {total_snaps:,}")
    print(f"  written last {window_min}m   : {recent_snaps:,}  ({snaps_per_min:.0f}/min)")
    mode_label = (
        f"WEEKLY densify (~{snaps_per_card} snaps/card)"
        if weekly_mode
        else f"MONTHLY resolve (~{snaps_per_card} snaps/card)"
    )
    print(f"  mode (auto)       : {mode_label}")
    if log_progress is not None:
        cur, tot, log_name = log_progress
        print(f"  weekly progress   : {cur:,}/{tot:,}  ({weekly_pct:.1f}%)  [from {log_name}]")
    if recent_snaps == 0:
        print(f"  STATUS            : no activity in window - backfill may be stalled or finished")
    else:
        eta_label = f"~{eta_min:.0f}min" if eta_min < 60 else f"~{eta_min/60:.1f}h"
        print(f"  ETA (rough)       : {eta_label} remaining ({cards_per_min:.0f} cards/min)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-min", type=int, default=30,
                        help="Window for 'recent activity' check (default 30 min)")
    args = parser.parse_args()
    asyncio.run(main(args.window_min))
