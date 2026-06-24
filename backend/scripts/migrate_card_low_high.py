"""Add `low_price_usd` + `high_price_usd` columns to `cards` and
backfill them from each card's existing `tcgplayer_prices` JSON.
Idempotent — safe to re-run; the daily TCGCSV sync keeps them
up to date going forward.

Why:
    Set page wants a "$X – $Y" completion-cost range — the cheapest
    possible set completion vs the most expensive — instead of a flat
    sum that means little to a collector. Summing per-card lows and
    highs at the set level needs flat columns; doing it from the JSON
    blob at query time would unnest thousands of rows on every page
    load.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.models import Card  # noqa: E402
from app.services.ebay_client import (  # noqa: E402
    _DEFAULT_ABS_CEILING,
    _RARITY_ABS_CEILING,
)

log = logging.getLogger("migrate_card_low_high")


ALTERS = (
    "ALTER TABLE cards ADD COLUMN IF NOT EXISTS low_price_usd DOUBLE PRECISION",
    "ALTER TABLE cards ADD COLUMN IF NOT EXISTS high_price_usd DOUBLE PRECISION",
)


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _rarity_ceiling(rarity: str | None) -> float:
    if rarity and rarity in _RARITY_ABS_CEILING:
        return _RARITY_ABS_CEILING[rarity]
    return _DEFAULT_ABS_CEILING


def extract_low_high(
    prices: dict | None, rarity: str | None
) -> tuple[float | None, float | None]:
    """Per-card flat low/high derived from the per-variant prices blob.

    low  = cheapest 'low' across all variants (rarely manipulated, no cap)
    high = most expensive 'high' across all variants, capped by the
           rarity ceiling (drops outlier $10k-asks on a $5 common)
    """
    if not isinstance(prices, dict):
        return None, None
    lows: list[float] = []
    highs: list[float] = []
    cap = _rarity_ceiling(rarity)
    for variant in prices.values():
        if not isinstance(variant, dict):
            continue
        lo = _f(variant.get("low"))
        hi = _f(variant.get("high"))
        if lo is not None:
            lows.append(lo)
        if hi is not None and hi <= cap:
            highs.append(hi)
    return (min(lows) if lows else None, max(highs) if highs else None)


async def main() -> None:
    async with engine.begin() as conn:
        for stmt in ALTERS:
            log.info("running: %s", stmt)
            await conn.execute(text(stmt))

    log.info("backfilling low/high from existing tcgplayer_prices JSON...")
    updated = 0
    skipped = 0
    async with SessionLocal() as db:
        cards = (await db.execute(select(Card))).scalars().all()
        for card in cards:
            lo, hi = extract_low_high(card.tcgplayer_prices, card.rarity)
            if lo is None and hi is None:
                skipped += 1
                continue
            card.low_price_usd = lo
            card.high_price_usd = hi
            updated += 1
        await db.commit()

    log.info(
        "done — updated=%d skipped_no_prices=%d total=%d",
        updated, skipped, updated + skipped,
    )


if __name__ == "__main__":
    asyncio.run(main())
