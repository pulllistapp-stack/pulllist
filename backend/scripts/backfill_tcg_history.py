"""Backfill ~1 year of TCGplayer market price history per card.

Hits the same `infinite-api.tcgplayer.com/price/history` endpoint that
TCGplayer's own product pages use, samples one snapshot per calendar
month from the 52 weekly buckets it returns, and writes them as
`CardPriceSnapshot` rows. Without this the 1Y chart range is empty
because our daily cron only started ~a week before launch.

Pipeline per card:
  1. card.tcgplayer_url is a pokemontcg.io redirect, not a canonical
     tcgplayer.com URL — follow it once to extract the numeric
     product_id (e.g. 662184).
  2. GET https://infinite-api.tcgplayer.com/price/history/{id}/detailed?range=annual
  3. Pick the Near Mint condition entry for the first available variant
     (priority: Normal -> Holofoil -> Reverse Holofoil -> first).
  4. Group its weekly buckets by year-month, pick the LAST bucket of
     each month as the representative point, write one snapshot row per
     month dated to the bucketStartDate.

Idempotent — uses ON CONFLICT DO NOTHING on (card_id, source, variant,
snapshot_date), so re-runs only fill in gaps. Rate-limited so we don't
hammer TCGplayer's API; defaults are conservative (500ms / call =
~2 req/sec, well below what their own product pages generate).

Usage:
    python -m scripts.backfill_tcg_history --limit 20      # smoke test
    python -m scripts.backfill_tcg_history --min-price 5   # skip junk
    python -m scripts.backfill_tcg_history                 # full
    python -m scripts.backfill_tcg_history --throttle-ms 700
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot
from scripts.sync_tcgplayer_prices import _clip_tcg_band

log = logging.getLogger("backfill_tcg_history")

HISTORY_API = "https://infinite-api.tcgplayer.com/price/history/{product_id}/detailed?range=annual"
PRODUCT_ID_RE = re.compile(r"tcgplayer\.com/product/(\d+)", re.IGNORECASE)
SOURCE = "tcgplayer"

# Variant preference — we backfill ONE variant per card (the chart's
# `combinedPoints` collapses across variants anyway, and writing all
# variants would 3-5x the row count).
VARIANT_PRIORITY = ("Normal", "Holofoil", "Reverse Holofoil", "1st Edition Holofoil")
# Condition preference — Near Mint is the canonical "market" reference;
# falls back to LP/MP if a card never had any NM sales.
CONDITION_PRIORITY = ("Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged")


async def _follow_to_product_id(http: httpx.AsyncClient, url: str) -> int | None:
    """Resolve a pokemontcg.io redirect to its tcgplayer.com product id.

    pokemontcg.io's `tcgplayer_url` is a 301 to the canonical TCGplayer
    product URL. We don't store the product_id anywhere; do the cheap
    lookup once and extract the numeric id from the final URL.
    """
    try:
        resp = await http.head(url, follow_redirects=True, timeout=15.0)
        final = str(resp.url)
        m = PRODUCT_ID_RE.search(final)
        if m:
            return int(m.group(1))
        # Some pokemontcg.io entries already point directly at TCGplayer;
        # try matching the input URL too.
        m = PRODUCT_ID_RE.search(url)
        if m:
            return int(m.group(1))
        return None
    except httpx.HTTPError:
        return None


async def _fetch_history(http: httpx.AsyncClient, product_id: int) -> list[dict] | None:
    """Pull the 1-year detailed history for a TCGplayer product."""
    try:
        resp = await http.get(
            HISTORY_API.format(product_id=product_id),
            timeout=30.0,
        )
        if resp.status_code == 404:
            return None  # product retired
        if resp.status_code == 429:
            # Hit the rate limit — sleep then retry once.
            await asyncio.sleep(5.0)
            resp = await http.get(
                HISTORY_API.format(product_id=product_id),
                timeout=30.0,
            )
        resp.raise_for_status()
        body = resp.json()
        return body.get("result") or []
    except (httpx.HTTPError, ValueError):
        return None


def _pick_per_variant_entries(entries: list[dict]) -> list[dict]:
    """For each distinct variant the API returns (Normal / Holofoil /
    Reverse Holofoil / etc.), pick the best-conditioned entry — Near
    Mint when present, else the next best. We backfill EVERY variant
    so the chart's daily snapshots (which write all variants) and our
    monthly history line up cleanly; otherwise a variant present in
    recent dailies but missing from backfill produces a phantom jump
    where the chart switches sources mid-timeline."""
    if not entries:
        return []
    by_variant: dict[str, dict[str, dict]] = {}
    for e in entries:
        v = e.get("variant") or ""
        c = e.get("condition") or ""
        by_variant.setdefault(v, {})[c] = e

    picked: list[dict] = []
    for v, conds in by_variant.items():
        chosen = None
        for c in CONDITION_PRIORITY:
            if c in conds:
                chosen = conds[c]
                break
        if chosen is None and conds:
            chosen = next(iter(conds.values()))
        if chosen is not None:
            picked.append(chosen)
    return picked


def _bucket_to_monthly(buckets: list[dict]) -> list[dict]:
    """Reduce ~52 weekly buckets to ~12 monthly samples.

    Picks the LAST bucket (most recent) within each year-month so the
    representative is the month-end price rather than month-start.
    """
    if not buckets:
        return []
    by_month: dict[str, dict] = {}
    for b in buckets:
        date_str = b.get("bucketStartDate")
        if not date_str:
            continue
        month_key = date_str[:7]  # "YYYY-MM"
        prev = by_month.get(month_key)
        if prev is None or date_str > prev["bucketStartDate"]:
            by_month[month_key] = b
    return sorted(by_month.values(), key=lambda b: b["bucketStartDate"])


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _conflict_insert(dialect_name: str):
    if dialect_name == "postgresql":
        return pg_insert(CardPriceSnapshot)
    return sqlite_insert(CardPriceSnapshot)


async def _flush(db: AsyncSession, batch: list[dict]) -> int:
    if not batch:
        return 0
    stmt = _conflict_insert(db.bind.dialect.name).values(batch)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["card_id", "source", "variant", "snapshot_date"]
    )
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount or 0


async def run(
    *,
    limit: int | None,
    min_price: float,
    throttle_ms: int,
) -> None:
    await init_db()
    throttle = throttle_ms / 1000.0

    async with SessionLocal() as db:
        stmt = (
            select(Card)
            .where(Card.tcgplayer_url.is_not(None))
            .where(Card.language == "en")
            .order_by(Card.market_price_usd.desc().nullslast())
        )
        if min_price > 0:
            stmt = stmt.where(Card.market_price_usd >= min_price)
        if limit:
            stmt = stmt.limit(limit)

        candidates = list((await db.execute(stmt)).scalars())
        log.info(f"Selected {len(candidates)} candidates (min_price=${min_price})")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PullList/1.0; +https://pulllist.org)",
        "Accept": "application/json",
    }

    stats = {
        "scanned": 0,
        "no_product_id": 0,
        "no_history": 0,
        "no_variant_match": 0,
        "snapshots_written": 0,
    }

    async with httpx.AsyncClient(headers=headers) as http:
        rows_batch: list[dict] = []
        for i, card in enumerate(candidates, 1):
            stats["scanned"] += 1

            product_id = await _follow_to_product_id(http, card.tcgplayer_url)
            if product_id is None:
                stats["no_product_id"] += 1
                if throttle:
                    await asyncio.sleep(throttle / 2)
                continue
            # Store the resolved product_id so the affiliate link wrapper
            # can route Buy clicks straight to the product page instead of
            # falling back to a search URL. Idempotent — skip when the
            # card already has the same id stored.
            if card.tcgplayer_product_id != product_id:
                async with SessionLocal() as ws:
                    await ws.execute(
                        update(Card)
                        .where(Card.id == card.id)
                        .values(tcgplayer_product_id=product_id)
                    )
                    await ws.commit()
            if throttle:
                await asyncio.sleep(throttle)

            entries = await _fetch_history(http, product_id)
            if not entries:
                stats["no_history"] += 1
                if throttle:
                    await asyncio.sleep(throttle)
                continue

            chosen_entries = _pick_per_variant_entries(entries)
            if not chosen_entries:
                stats["no_variant_match"] += 1
                continue

            for entry in chosen_entries:
                # Match the sync script's variant naming: API uses
                # "Holofoil" / "Reverse Holofoil"; pokemontcg.io uses
                # camelCase like "holofoil" / "reverseHolofoil". Map.
                raw_variant = (entry.get("variant") or "Normal").strip()
                variant = {
                    "Normal": "normal",
                    "Holofoil": "holofoil",
                    "Reverse Holofoil": "reverseHolofoil",
                    "1st Edition Holofoil": "1stEditionHolofoil",
                    "1st Edition": "1stEdition",
                    "Unlimited Holofoil": "unlimitedHolofoil",
                }.get(raw_variant, raw_variant.lower().replace(" ", ""))

                monthly = _bucket_to_monthly(entry.get("buckets", []))
                for b in monthly:
                    date_str = b["bucketStartDate"]
                    market = _f(b.get("marketPrice"))
                    # Skip buckets with no trading activity — vintage
                    # cards have many empty months and writing $0 rows
                    # poisons the chart.
                    if market is None or market <= 0:
                        continue
                    low = _f(b.get("lowSalePrice"))
                    high = _f(b.get("highSalePrice"))
                    # Same defensive treatment for low/high — these
                    # arrive as 0 when there were no sales in the bucket.
                    if low is not None and low <= 0:
                        low = None
                    if high is not None and high <= 0:
                        high = None
                    # Apply the same band-clip the daily sync uses so
                    # backfilled rows don't need a separate cleanup pass.
                    low, high = _clip_tcg_band(market, low, high, card.rarity)
                    rows_batch.append(
                        {
                            "card_id": card.id,
                            "source": SOURCE,
                            "variant": variant,
                            "market_price_usd": market,
                            "low_price_usd": low,
                            "mid_price_usd": market,
                            "high_price_usd": high,
                            "sales_count": int(_f(b.get("quantitySold")) or 0) or None,
                            "snapshot_at": datetime.utcnow(),
                            "snapshot_date": date_str,
                        }
                    )

            if len(rows_batch) >= 200:
                async with SessionLocal() as db:
                    stats["snapshots_written"] += await _flush(db, rows_batch)
                rows_batch.clear()

            if i % 50 == 0:
                log.info(
                    f"  [{i}/{len(candidates)}] last={card.name[:30]} "
                    f"writes={stats['snapshots_written']} "
                    f"no_id={stats['no_product_id']} no_hist={stats['no_history']}"
                )

            if throttle:
                await asyncio.sleep(throttle)

        if rows_batch:
            async with SessionLocal() as db:
                stats["snapshots_written"] += await _flush(db, rows_batch)

    log.info(
        "\n=== Backfill summary ===\n"
        f"  Cards scanned          : {stats['scanned']}\n"
        f"  Skipped (no product_id): {stats['no_product_id']}\n"
        f"  Skipped (no history)   : {stats['no_history']}\n"
        f"  Skipped (no variant)   : {stats['no_variant_match']}\n"
        f"  Snapshots written      : {stats['snapshots_written']}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Cap number of cards (smoke test)")
    parser.add_argument("--min-price", type=float, default=1.0, help="Skip cards below this market price")
    parser.add_argument("--throttle-ms", type=int, default=500, help="Sleep between API calls (default 500ms = ~2 req/sec)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(
        run(limit=args.limit, min_price=args.min_price, throttle_ms=args.throttle_ms)
    )


if __name__ == "__main__":
    main()
