"""Daily TCGplayer price sync via TCGCSV.

TCGCSV (tcgcsv.com) republishes TCGplayer's daily price snapshots through
a free JSON API. We use it instead of pokemontcg.io for TCGplayer prices
because:
  - Updates daily (UTC 20:00) vs pokemontcg.io's ~weekly cadence
  - No deprecation risk hanging over pokemontcg.io v2
  - Same upstream source (TCGplayer) so values match

This script handles TCGplayer only. Cardmarket prices still come from
the pokemontcg.io sync (sync_tcgplayer_prices.py) — TCGCSV doesn't have
Cardmarket data and Cardmarket's own data is fiddly to parse.

For each Pokemon group on TCGCSV:
  1. GET /tcgplayer/3/{groupId}/prices  → list of {productId, subTypeName, ...}
  2. Group rows by productId, transform to our per-variant tcgplayer_prices JSON
  3. Find matching card by tcgplayer_product_id, update card row + insert snapshot

Idempotent — ON CONFLICT DO NOTHING on snapshots, plain UPDATE on cards.

Usage:
    python -m scripts.sync_tcgcsv_daily              # daily full sync
    python -m scripts.sync_tcgcsv_daily --dry-run    # report only
    python -m scripts.sync_tcgcsv_daily --date 2026-06-15  # use specific date

Attribution: data from https://tcgcsv.com (CptSpaceToaster).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

# Mute SQLAlchemy echo on dev — settings.debug=True drowns out our progress log.
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.models import Card, CardPriceSnapshot  # noqa: E402

engine.echo = False
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

log = logging.getLogger("sync_tcgcsv_daily")
log.setLevel(logging.INFO)


TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
POKEMON_CATEGORY = "3"
USER_AGENT = "PullList/1.0 (https://pulllist.org; LO)"
SOURCE_TCGPLAYER = "tcgplayer"

# TCGCSV subTypeName -> our variant column / tcgplayer_prices JSON key
VARIANT_MAP = {
    "Normal": "normal",
    "Foil": "holofoil",
    "Holofoil": "holofoil",
    "Reverse Holofoil": "reverseHolofoil",
    "1st Edition": "1stEdition",
    "1st Edition Holofoil": "1stEditionHolofoil",
    "Unlimited": "unlimited",
    "Unlimited Holofoil": "unlimitedHolofoil",
}

# Same priority used by the original pokemontcg.io sync, replicated here so the
# denormalized cards.market_price_usd field stays consistent across sources.
VARIANT_PRIORITY = (
    "normal",
    "holofoil",
    "reverseHolofoil",
    "1stEditionHolofoil",
    "1stEdition",
    "unlimitedHolofoil",
    "unlimited",
)


def _f(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return f


def _market_from_prices(prices: dict) -> float | None:
    """Pick the base variant's market price following the same priority
    as the pokemontcg.io sync — keeps cards.market_price_usd consistent
    no matter which source last touched the row."""
    for key in VARIANT_PRIORITY:
        variant = prices.get(key)
        if not isinstance(variant, dict):
            continue
        m = variant.get("market") or variant.get("mid")
        if isinstance(m, (int, float)) and m > 0:
            return float(m)
    for variant in prices.values():
        if not isinstance(variant, dict):
            continue
        m = variant.get("market") or variant.get("mid")
        if isinstance(m, (int, float)) and m > 0:
            return float(m)
    return None


def _group_rows_by_product(rows: list[dict]) -> dict[int, dict]:
    """Collapse TCGCSV's flat (product, subType) rows into our nested
    per-variant tcgplayer_prices format:
        {productId: {"normal": {"low": .., "mid": .., "high": .., "market": ..,
                                 "directLow": ..}, "holofoil": {...}, ...}}
    """
    out: dict[int, dict] = {}
    for entry in rows:
        product_id = entry.get("productId")
        if product_id is None:
            continue
        variant = VARIANT_MAP.get(entry.get("subTypeName"))
        if not variant:
            continue
        market = _f(entry.get("marketPrice"))
        mid = _f(entry.get("midPrice"))
        if market is None and mid is None:
            continue
        bucket = out.setdefault(product_id, {})
        bucket[variant] = {
            "low": _f(entry.get("lowPrice")),
            "mid": mid,
            "high": _f(entry.get("highPrice")),
            "market": market,
            "directLow": _f(entry.get("directLowPrice")),
        }
    return out


def _conflict_insert(dialect_name: str):
    if dialect_name == "postgresql":
        return pg_insert(CardPriceSnapshot)
    return sqlite_insert(CardPriceSnapshot)


def _snapshot_rows(card_id: str, prices: dict, snapshot_date: str) -> list[dict]:
    """One snapshot row per variant — keeps trending / chart logic happy."""
    rows = []
    for variant, payload in prices.items():
        market = payload.get("market") or payload.get("mid")
        if market is None:
            continue
        rows.append({
            "card_id": card_id,
            "source": SOURCE_TCGPLAYER,
            "variant": variant,
            "market_price_usd": float(market),
            "low_price_usd": payload.get("low"),
            "mid_price_usd": payload.get("mid"),
            "high_price_usd": payload.get("high"),
            "sales_count": None,
            "snapshot_at": datetime.utcnow(),
            "snapshot_date": snapshot_date,
        })
    return rows


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.get(url, timeout=60.0)
    r.raise_for_status()
    return r.json()


async def _list_pokemon_groups(client: httpx.AsyncClient) -> list[dict]:
    data = await _fetch_json(client, f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/groups")
    return data.get("results", [])


async def _group_prices(client: httpx.AsyncClient, group_id: int) -> list[dict]:
    data = await _fetch_json(
        client, f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/{group_id}/prices"
    )
    return data.get("results", [])


async def _load_product_map(db: AsyncSession) -> dict[int, str]:
    stmt = select(Card.id, Card.tcgplayer_product_id).where(
        Card.tcgplayer_product_id.isnot(None)
    )
    rows = (await db.execute(stmt)).all()
    return {pid: cid for cid, pid in rows if pid is not None}


async def _flush_snapshots(db: AsyncSession, batch: list[dict]) -> int:
    if not batch:
        return 0
    dialect_name = db.bind.dialect.name
    stmt = _conflict_insert(dialect_name).values(batch).on_conflict_do_nothing(
        index_elements=["card_id", "source", "variant", "snapshot_date"]
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def sync(snapshot_date: str, dry_run: bool, group_limit: int | None) -> None:
    await init_db()
    async with SessionLocal() as db:
        product_to_card = await _load_product_map(db)
    log.info(f"loaded {len(product_to_card)} tcgplayer_product_id mappings")

    stats = {
        "groups_seen": 0,
        "products_seen": 0,
        "cards_refreshed": 0,
        "cards_missing": 0,
        "snapshots_inserted": 0,
        "group_errors": 0,
    }

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        groups = await _list_pokemon_groups(client)
        if group_limit:
            groups = groups[:group_limit]
        log.info(f"{len(groups)} pokemon groups to sync")

        for idx, group in enumerate(groups, 1):
            group_id = group.get("groupId")
            group_name = group.get("name") or str(group_id)
            stats["groups_seen"] += 1
            try:
                price_rows = await _group_prices(client, group_id)
            except Exception as exc:
                log.warning(f"[{idx}/{len(groups)}] {group_name}: fetch failed ({exc})")
                stats["group_errors"] += 1
                continue

            by_product = _group_rows_by_product(price_rows)
            stats["products_seen"] += len(by_product)
            if not by_product:
                continue

            snapshot_batch: list[dict] = []
            async with SessionLocal() as db:
                for product_id, prices in by_product.items():
                    card_id = product_to_card.get(product_id)
                    if not card_id:
                        stats["cards_missing"] += 1
                        continue
                    existing = await db.get(Card, card_id)
                    if existing is None:
                        stats["cards_missing"] += 1
                        continue

                    market = _market_from_prices(prices)
                    if not dry_run:
                        existing.tcgplayer_prices = prices
                        if market is not None:
                            existing.market_price_usd = market

                    stats["cards_refreshed"] += 1
                    snapshot_batch.extend(_snapshot_rows(card_id, prices, snapshot_date))

                if not dry_run:
                    await db.commit()
                    written = await _flush_snapshots(db, snapshot_batch)
                    stats["snapshots_inserted"] += written

            log.info(
                f"[{idx}/{len(groups)}] {group_name}: {len(by_product)} products, "
                f"{stats['snapshots_inserted']} total snapshots"
            )
            # Be polite — TCGCSV asks for 250ms between requests
            await asyncio.sleep(0.25)

    log.info(f"=== sync summary ({snapshot_date}) ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    log.info(f"  dry_run: {dry_run}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", dest="snapshot_date",
        help="YYYY-MM-DD (defaults to today UTC).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch + parse, but don't write to the DB.",
    )
    parser.add_argument(
        "--limit-groups", type=int, default=None,
        help="Process only the first N groups (smoke testing).",
    )
    args = parser.parse_args()
    snapshot_date = args.snapshot_date or date.today().isoformat()
    asyncio.run(sync(snapshot_date, args.dry_run, args.limit_groups))


if __name__ == "__main__":
    main()
