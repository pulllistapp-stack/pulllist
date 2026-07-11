"""Daily price snapshot.

Walks every card and creates a `card_price_snapshots` row per (source, variant)
based on the latest pokemontcg.io / TCGplayer data we already have on the card.
Skips cards that already have today's snapshot (idempotent — safe to re-run).

Usage:
    python -m scripts.snapshot_prices              # today, all cards
    python -m scripts.snapshot_prices --date 2026-06-10   # backfill date
    python -m scripts.snapshot_prices --limit 100  # smoke test

Future: when eBay/TCGplayer-direct/Scrydex keys arrive, add another
`collect_from_*` function and call it in `run()`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot

SOURCE_TCGPLAYER = "tcgplayer"
SOURCE_CARDMARKET = "cardmarket"


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_from_tcgplayer(card: Card, snapshot_date: str) -> list[dict]:
    """Extract one snapshot row per TCGplayer variant (normal/holo/reverse/...)."""
    if not card.tcgplayer_prices:
        return []
    rows = []
    for variant, payload in card.tcgplayer_prices.items():
        if not isinstance(payload, dict):
            continue
        market = _f(payload.get("market")) or _f(payload.get("mid"))
        if market is None and _f(payload.get("low")) is None:
            continue
        rows.append(
            {
                "card_id": card.id,
                "source": SOURCE_TCGPLAYER,
                "variant": variant,
                "market_price_usd": market,
                "low_price_usd": _f(payload.get("low")),
                "mid_price_usd": _f(payload.get("mid")),
                "high_price_usd": _f(payload.get("high")),
                "sales_count": None,
                "snapshot_at": datetime.utcnow(),
                "snapshot_date": snapshot_date,
            }
        )
    return rows


def collect_from_cardmarket(card: Card, snapshot_date: str) -> list[dict]:
    """Cardmarket gives a flat dict of named prices (no variant breakdown)."""
    prices = card.cardmarket_prices
    if not prices:
        return []
    market = _f(prices.get("trendPrice")) or _f(prices.get("averageSellPrice"))
    if market is None:
        return []
    return [
        {
            "card_id": card.id,
            "source": SOURCE_CARDMARKET,
            "variant": "trend",
            "market_price_usd": market,
            "low_price_usd": _f(prices.get("lowPrice")),
            "mid_price_usd": _f(prices.get("averageSellPrice")),
            "high_price_usd": None,
            "sales_count": None,
            "snapshot_at": datetime.utcnow(),
            "snapshot_date": snapshot_date,
        }
    ]


async def snapshot_all(db: AsyncSession, snapshot_date: str, limit: int | None) -> int:
    stmt = select(Card)
    if limit:
        stmt = stmt.limit(limit)

    total_inserted = 0
    batch: list[dict] = []
    batch_size = 500
    processed = 0

    async for card in (await db.stream_scalars(stmt)):
        rows = collect_from_tcgplayer(card, snapshot_date) + collect_from_cardmarket(
            card, snapshot_date
        )
        batch.extend(rows)
        processed += 1

        if len(batch) >= batch_size:
            total_inserted += await flush(db, batch)
            batch.clear()

        if processed % 2000 == 0:
            print(f"  Processed {processed} cards, inserted {total_inserted} snapshots so far…")

    if batch:
        total_inserted += await flush(db, batch)

    print(f"Processed {processed} cards.")
    print(f"Inserted {total_inserted} new snapshot rows.")
    return total_inserted


async def flush(db: AsyncSession, batch: list[dict]) -> int:
    """Insert-or-ignore so re-runs are idempotent (unique constraint per day)."""
    if not batch:
        return 0
    stmt = sqlite_insert(CardPriceSnapshot).values(batch)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["card_id", "source", "variant", "grade", "snapshot_date"]
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def main_async(snapshot_date: str, limit: int | None) -> None:
    await init_db()
    async with SessionLocal() as db:
        print(f"Snapshotting prices for {snapshot_date}…")
        await snapshot_all(db, snapshot_date, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        dest="snapshot_date",
        help="YYYY-MM-DD (defaults to today UTC)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap card count")
    args = parser.parse_args()

    snapshot_date = args.snapshot_date or date.today().isoformat()
    asyncio.run(main_async(snapshot_date, args.limit))


if __name__ == "__main__":
    main()
