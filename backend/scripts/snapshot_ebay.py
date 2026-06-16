"""Daily eBay price snapshot.

Walks cards above a minimum price threshold, queries eBay Browse for each,
and writes a `card_price_snapshots` row per card (source='ebay', variant='active').

Rate-limit aware: throttles between calls, supports `--limit` and `--max-calls`
to stay well under the 5,000/day free-tier ceiling. Idempotent — skips cards
that already have today's eBay snapshot.

Usage:
    # Smoke test (5 cards, dry run prints what it WOULD save):
    python -m scripts.snapshot_ebay --limit 5 --dry-run

    # Real run, default settings (all cards with market_price >= $5):
    python -m scripts.snapshot_ebay

    # Tight budget — only 200 calls today, prefer expensive cards first:
    python -m scripts.snapshot_ebay --max-calls 200 --min-price 20

    # Backfill date (still hits eBay's *current* prices, just labels them):
    python -m scripts.snapshot_ebay --date 2026-06-13
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot, Set
from app.services.ebay_client import EbayClient, EbayClientError, build_card_query

log = logging.getLogger("snapshot_ebay")

SOURCE = "ebay"
VARIANT_ACTIVE = "active"


async def already_snapshotted_today(
    db: AsyncSession, card_id: str, snapshot_date: str
) -> bool:
    stmt = (
        select(CardPriceSnapshot.id)
        .where(
            CardPriceSnapshot.card_id == card_id,
            CardPriceSnapshot.source == SOURCE,
            CardPriceSnapshot.variant == VARIANT_ACTIVE,
            CardPriceSnapshot.snapshot_date == snapshot_date,
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.scalar() is not None


async def collect_from_ebay(
    ebay: EbayClient,
    card: Card,
    set_: Set | None,
    snapshot_date: str,
) -> dict | None:
    """Fetch eBay price summary for one card and return a snapshot row dict.

    Returns None if no listings found (no row written). On a miss we log a
    compact drop-reason summary so workflow logs are debuggable without
    re-running the inspect script.
    """
    query = build_card_query(
        card_name=card.name,
        card_number=card.number,
        printed_total=set_.printed_total if set_ else None,
        set_name=set_.name if set_ else None,
        rarity=card.rarity,
    )

    reference_price = (
        float(card.market_price_usd) if card.market_price_usd is not None else None
    )
    detail = await ebay.price_summary_with_trace(
        query,
        max_results=50,
        reference_price_usd=reference_price,
        card_number=card.number,
        rarity=card.rarity,
    )
    summary = detail["summary"]
    if summary is None:
        # Tally drop reasons across every pass so the workflow log explains
        # the miss in one line: "fetched=N kept=K drops={...}".
        cls = [c for p in detail["passes"] for c in p["classifications"]]
        kept = sum(1 for c in cls if c.kept)
        drops: dict[str, int] = {}
        for c in cls:
            if not c.kept and c.drop_reason:
                key = c.drop_reason.split(":", 1)[0]
                drops[key] = drops.get(key, 0) + 1
        log.info(
            f"{card.id} ({card.name[:30]}) — no usable listings  "
            f"fetched={len(cls)} kept={kept} min_required={detail['min_required']} "
            f"drops={drops}"
        )
        return None

    return {
        "card_id": card.id,
        "source": SOURCE,
        "variant": VARIANT_ACTIVE,
        "market_price_usd": float(summary["median"]),
        "low_price_usd": float(summary["low"]),
        "mid_price_usd": float(summary["median"]),
        "high_price_usd": float(summary["high"]),
        "sales_count": None,  # Browse API gives active listings only — sold count needs Marketplace Insights
        "snapshot_at": datetime.utcnow(),
        "snapshot_date": snapshot_date,
    }


async def run_snapshot(
    *,
    snapshot_date: str,
    min_price: float,
    limit: int | None,
    max_calls: int,
    throttle_ms: int,
    dry_run: bool,
    set_ids: list[str] | None = None,
) -> None:
    await init_db()

    async with SessionLocal() as db:
        # Build the candidate filter. Two modes:
        #   1) `--set-ids me4,me3,...`   → all en cards in those sets, INCLUDING null prices
        #      (this is the path to backfill the pokemontcg.io gap for newest sets).
        #   2) default                    → en cards with market_price >= min_price
        #      (covers everything else, prioritising expensive cards).
        stmt = (
            select(Card)
            .options(selectinload(Card.set))
            .where(Card.language == "en")
        )
        if set_ids:
            stmt = stmt.where(Card.set_id.in_(set_ids)).order_by(
                Card.market_price_usd.desc().nullslast(),
                Card.number_int.asc().nullslast(),
            )
        else:
            stmt = stmt.where(Card.market_price_usd >= min_price).order_by(
                Card.market_price_usd.desc()
            )
        if limit:
            stmt = stmt.limit(limit)

        candidates = list((await db.execute(stmt)).scalars())
        mode_desc = (
            f"set_ids={set_ids} (incl. NULL prices)"
            if set_ids
            else f"market>={min_price}"
        )
        log.info(f"Selected {len(candidates)} candidate cards (lang=en, {mode_desc})")

        calls_made = 0
        snapshots_written = 0
        skipped_existing = 0
        empty_listings = 0
        errors = 0
        rows_batch: list[dict] = []
        batch_size = 100
        throttle_sec = throttle_ms / 1000.0

        async with EbayClient() as ebay:
            for i, card in enumerate(candidates, 1):
                if calls_made >= max_calls:
                    log.warning(f"hit max_calls={max_calls} budget — stopping early")
                    break

                # idempotency
                if await already_snapshotted_today(db, card.id, snapshot_date):
                    skipped_existing += 1
                    continue

                try:
                    row = await collect_from_ebay(ebay, card, card.set, snapshot_date)
                    calls_made += 1
                except EbayClientError as e:
                    errors += 1
                    log.warning(f"{card.id} {card.name!r}: {e}")
                    continue
                except Exception as e:
                    errors += 1
                    log.exception(f"{card.id} {card.name!r}: unexpected: {e}")
                    continue

                if row is None:
                    empty_listings += 1
                else:
                    rows_batch.append(row)
                    log.info(
                        f"[{i}/{len(candidates)}] {card.id} {card.name[:40]:40s} "
                        f"low={row['low_price_usd']:.2f} median={row['market_price_usd']:.2f} "
                        f"high={row['high_price_usd']:.2f}"
                    )

                    # Backfill the denormalized Card.market_price_usd when it's NULL
                    # (so the catalog/grid UI shows a price for sets pokemontcg.io
                    # hasn't synced yet). Never overwrite an existing tcgplayer-derived value.
                    if card.market_price_usd is None and not dry_run:
                        await db.execute(
                            update(Card)
                            .where(Card.id == card.id)
                            .where(Card.market_price_usd.is_(None))
                            .values(market_price_usd=row["market_price_usd"])
                        )

                if len(rows_batch) >= batch_size:
                    if not dry_run:
                        snapshots_written += await _flush(db, rows_batch)
                    else:
                        snapshots_written += len(rows_batch)
                    rows_batch.clear()

                if throttle_sec > 0:
                    await asyncio.sleep(throttle_sec)

        if rows_batch:
            if not dry_run:
                snapshots_written += await _flush(db, rows_batch)
            else:
                snapshots_written += len(rows_batch)

        log.info(
            f"\n=== eBay snapshot summary ({snapshot_date}) ===\n"
            f"  Candidates considered  : {len(candidates)}\n"
            f"  Already done today     : {skipped_existing}\n"
            f"  eBay calls made        : {calls_made}\n"
            f"  Snapshots written      : {snapshots_written}\n"
            f"  No listings (skipped)  : {empty_listings}\n"
            f"  Errors                 : {errors}\n"
            f"  Dry run                : {dry_run}\n"
        )


def _conflict_insert(dialect_name: str):
    """ON CONFLICT DO NOTHING — picks the right dialect (postgres or sqlite)."""
    if dialect_name == "postgresql":
        return pg_insert(CardPriceSnapshot)
    return sqlite_insert(CardPriceSnapshot)


async def _flush(db: AsyncSession, batch: list[dict]) -> int:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", dest="snapshot_date", help="YYYY-MM-DD (defaults to today UTC)")
    parser.add_argument("--limit", type=int, default=None, help="Cap candidate cards")
    parser.add_argument("--max-calls", type=int, default=4500, help="Max eBay API calls this run (free tier ~5000/day, default 4500 for safety)")
    parser.add_argument("--min-price", type=float, default=5.0, help="Skip cards below this market_price_usd (default 5.0)")
    parser.add_argument("--throttle-ms", type=int, default=150, help="Sleep between calls in ms (default 150 = ~6 calls/sec)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be saved, don't write to DB")
    parser.add_argument("--set-ids", default=None, help="Comma-separated set IDs to backfill (overrides --min-price; includes NULL-priced cards)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    snapshot_date = args.snapshot_date or date.today().isoformat()
    set_ids = [s.strip() for s in args.set_ids.split(",")] if args.set_ids else None
    asyncio.run(
        run_snapshot(
            snapshot_date=snapshot_date,
            min_price=args.min_price,
            limit=args.limit,
            max_calls=args.max_calls,
            throttle_ms=args.throttle_ms,
            dry_run=args.dry_run,
            set_ids=set_ids,
        )
    )


if __name__ == "__main__":
    main()
