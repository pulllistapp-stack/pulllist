"""Daily TCGplayer + Cardmarket price sync via pokemontcg.io.

Refreshes price fields on existing cards from pokemontcg.io (which mirrors
TCGplayer + Cardmarket pricing) and writes today's snapshot rows to
`card_price_snapshots`. Idempotent — re-runs skip cards that already have a
snapshot for the same (source, variant, date).

Why pokemontcg.io rather than TCGplayer direct? TCGplayer closed new API
access after the eBay acquisition. pokemontcg.io maintains an official
partnership and exposes the same TCGplayer market/low/mid/high pricing
through a free, well-rate-limited public API.

Usage:
    # Daily full sync (all seeded sets)
    python -m scripts.sync_tcgplayer_prices

    # Smoke test: one set, dry run prints what would be written
    python -m scripts.sync_tcgplayer_prices --set-ids me4 --dry-run

    # Refresh card price fields but skip writing snapshots
    python -m scripts.sync_tcgplayer_prices --skip-snapshots

    # Backfill a date (still uses *current* TCGplayer prices, just labels them)
    python -m scripts.sync_tcgplayer_prices --date 2026-06-13
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot, Set

log = logging.getLogger("sync_tcgplayer_prices")

POKEMONTCG_BASE = "https://api.pokemontcg.io/v2"

SOURCE_TCGPLAYER = "tcgplayer"
SOURCE_CARDMARKET = "cardmarket"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/json"}
    if settings.pokemontcg_api_key:
        h["X-Api-Key"] = settings.pokemontcg_api_key
    return h


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _market_price_from_tcgplayer(prices: dict | None) -> float | None:
    """Pick the largest market/mid across variants — mirrors seed_sets behavior."""
    if not prices:
        return None
    best: float | None = None
    for variant in prices.values():
        if not isinstance(variant, dict):
            continue
        market = variant.get("market") or variant.get("mid")
        if isinstance(market, (int, float)):
            if best is None or market > best:
                best = float(market)
    return best


async def fetch_cards_for_set(
    client: httpx.AsyncClient, set_id: str
) -> list[dict]:
    """All cards in a set, paginated 250 at a time (pokemontcg.io max)."""
    all_cards: list[dict] = []
    page = 1
    while True:
        resp = await client.get(
            f"{POKEMONTCG_BASE}/cards",
            headers=_headers(),
            params={"q": f"set.id:{set_id}", "page": page, "pageSize": 250},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        all_cards.extend(data)
        if len(data) < 250:
            break
        page += 1
    return all_cards


def collect_tcgplayer_snapshots(
    card_id: str, prices: dict | None, snapshot_date: str
) -> list[dict]:
    if not prices:
        return []
    rows = []
    for variant, payload in prices.items():
        if not isinstance(payload, dict):
            continue
        market = _f(payload.get("market")) or _f(payload.get("mid"))
        if market is None and _f(payload.get("low")) is None:
            continue
        rows.append(
            {
                "card_id": card_id,
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


def collect_cardmarket_snapshots(
    card_id: str, prices: dict | None, snapshot_date: str
) -> list[dict]:
    """Cardmarket gives flat named prices — no variant breakdown."""
    if not prices:
        return []
    market = _f(prices.get("trendPrice")) or _f(prices.get("averageSellPrice"))
    if market is None:
        return []
    return [
        {
            "card_id": card_id,
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


def _conflict_insert(dialect_name: str):
    """ON CONFLICT DO NOTHING dialect dispatch — pg in prod, sqlite locally."""
    if dialect_name == "postgresql":
        return pg_insert(CardPriceSnapshot)
    return sqlite_insert(CardPriceSnapshot)


async def _flush_snapshots(db: AsyncSession, batch: list[dict]) -> int:
    if not batch:
        return 0
    dialect_name = db.bind.dialect.name
    stmt = _conflict_insert(dialect_name).values(batch)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["card_id", "source", "variant", "snapshot_date"]
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def sync(
    set_ids: list[str] | None,
    dry_run: bool,
    skip_snapshots: bool,
    snapshot_date: str,
) -> None:
    await init_db()

    async with SessionLocal() as db:
        sets_stmt = select(Set.id).order_by(Set.release_date.desc().nullslast())
        if set_ids:
            sets_stmt = sets_stmt.where(Set.id.in_(set_ids))
        existing_set_ids = (await db.execute(sets_stmt)).scalars().all()

    if not existing_set_ids:
        log.warning("No sets to sync (DB has no matching sets).")
        return

    log.info("Syncing TCGplayer + Cardmarket prices for %d sets…", len(existing_set_ids))

    stats = {
        "cards_seen": 0,
        "cards_refreshed": 0,
        "cards_missing": 0,
        "snapshots_inserted": 0,
        "set_errors": 0,
    }

    async with httpx.AsyncClient() as client:
        for idx, set_id in enumerate(existing_set_ids, start=1):
            log.info("[%d/%d] Fetching %s…", idx, len(existing_set_ids), set_id)
            try:
                raw_cards = await fetch_cards_for_set(client, set_id)
            except httpx.HTTPError as e:
                log.error("  ! Failed to fetch %s: %s", set_id, e)
                stats["set_errors"] += 1
                continue

            snapshot_batch: list[dict] = []

            async with SessionLocal() as db:
                for raw in raw_cards:
                    stats["cards_seen"] += 1
                    card_id = raw["id"]
                    tcgplayer = raw.get("tcgplayer", {}) or {}
                    cardmarket = raw.get("cardmarket", {}) or {}
                    tcg_prices = tcgplayer.get("prices")
                    cm_prices = cardmarket.get("prices")
                    market = _market_price_from_tcgplayer(tcg_prices)

                    existing = await db.get(Card, card_id)
                    if existing is None:
                        # Skip cards not in DB — sync script should not add new cards;
                        # use seed_sets.py for that.
                        stats["cards_missing"] += 1
                        continue

                    if not dry_run:
                        existing.tcgplayer_url = (
                            tcgplayer.get("url") or existing.tcgplayer_url
                        )
                        existing.tcgplayer_prices = tcg_prices
                        existing.cardmarket_url = (
                            cardmarket.get("url") or existing.cardmarket_url
                        )
                        existing.cardmarket_prices = cm_prices
                        # Only freshen market_price_usd when we got a non-null reading,
                        # so cards without TCGplayer pricing keep whatever they had.
                        if market is not None:
                            existing.market_price_usd = market

                    stats["cards_refreshed"] += 1

                    if not skip_snapshots:
                        snapshot_batch.extend(
                            collect_tcgplayer_snapshots(card_id, tcg_prices, snapshot_date)
                            + collect_cardmarket_snapshots(card_id, cm_prices, snapshot_date)
                        )

                if not dry_run:
                    await db.commit()

                if snapshot_batch and not dry_run:
                    written = await _flush_snapshots(db, snapshot_batch)
                    stats["snapshots_inserted"] += written
                    log.info(
                        "    refreshed %d cards, wrote %d snapshots",
                        len(raw_cards),
                        written,
                    )

    log.info("=== sync summary (%s) ===", snapshot_date)
    log.info("  Cards seen          : %d", stats["cards_seen"])
    log.info("  Cards refreshed     : %d", stats["cards_refreshed"])
    log.info("  Cards missing in DB : %d", stats["cards_missing"])
    log.info("  Snapshots inserted  : %d", stats["snapshots_inserted"])
    log.info("  Set fetch errors    : %d", stats["set_errors"])
    log.info("  Dry run             : %s", dry_run)
    log.info("  Skip snapshots      : %s", skip_snapshots)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--set-ids",
        help="Comma-separated set ids to limit sync (default: all seeded sets).",
    )
    parser.add_argument(
        "--date",
        dest="snapshot_date",
        help="YYYY-MM-DD (defaults to today UTC).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + parse, but don't write anything to the DB.",
    )
    parser.add_argument(
        "--skip-snapshots",
        action="store_true",
        help="Refresh card price fields but don't write snapshots.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Debug logs."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    set_ids = (
        [s.strip() for s in args.set_ids.split(",") if s.strip()]
        if args.set_ids
        else None
    )
    snapshot_date = args.snapshot_date or date.today().isoformat()

    asyncio.run(sync(set_ids, args.dry_run, args.skip_snapshots, snapshot_date))


if __name__ == "__main__":
    main()
