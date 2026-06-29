"""Add `mid_price_usd` column to `cards` and backfill from the
existing `tcgplayer_prices` JSON.

Why:
    Set-value headline shows a sum-of-prices total. We tried
    market_price_usd (TCGplayer sales-driven mid) — close to mid but
    not identical, and surprising when LO expected the literal mid
    column. We tried high_price_usd — catches graded slab listings
    and balloons the total. Mid is the unloved middle field; LO
    wants exactly that.

    Daily sync now populates this column going forward via
    _mid_from_prices(); this script handles the one-time backfill
    so existing rows don't sit at NULL until each card's next sync
    tick.

Idempotent — ALTER uses IF NOT EXISTS, backfill is a pure assign
from JSON so re-running is harmless.

Run:
    python -m scripts.migrate_card_mid_price
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.models import Card  # noqa: E402


log = logging.getLogger("migrate_card_mid_price")


ALTER = (
    "ALTER TABLE cards "
    "ADD COLUMN IF NOT EXISTS mid_price_usd DOUBLE PRECISION"
)


# Variant priority — same order as _market_from_prices in
# sync_tcgcsv_daily so the "headline mid" tracks the same variant
# the headline market does (no surprise cross-variant skew when LO
# eyeballs a card vs the set total).
_VARIANT_PRIORITY = (
    "normal",
    "holofoil",
    "reverseHolofoil",
    "1stEdition",
    "1stEditionHolofoil",
    "unlimited",
    "unlimitedHolofoil",
)


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def extract_mid(prices: dict | None) -> float | None:
    if not isinstance(prices, dict):
        return None
    # Try base-variant order first
    for key in _VARIANT_PRIORITY:
        variant = prices.get(key)
        if isinstance(variant, dict):
            m = _f(variant.get("mid"))
            if m is not None:
                return m
    # Fall through to any variant
    for variant in prices.values():
        if isinstance(variant, dict):
            m = _f(variant.get("mid"))
            if m is not None:
                return m
    return None


async def main() -> None:
    async with engine.begin() as conn:
        log.info("running: %s", ALTER)
        await conn.execute(text(ALTER))

    log.info("backfilling mid_price_usd from existing tcgplayer_prices JSON...")
    updated = 0
    skipped = 0
    async with SessionLocal() as db:
        cards = (await db.execute(select(Card))).scalars().all()
        for card in cards:
            mid = extract_mid(card.tcgplayer_prices)
            if mid is None:
                skipped += 1
                continue
            card.mid_price_usd = mid
            updated += 1
        await db.commit()

    log.info(
        "done — updated=%d skipped_no_mid=%d total=%d",
        updated, skipped, updated + skipped,
    )


if __name__ == "__main__":
    asyncio.run(main())
