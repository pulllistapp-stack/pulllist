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
from app.services.grade_classifier import classify_grade

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


MIN_LISTINGS_PER_GRADE = 2
"""Minimum kept listings needed to compute a stable median for a grade
bucket. Below this the bucket is dropped rather than surface a single
outlier as "the graded price". Raw bucket usually clears easily;
psa10/psa9/cgc10 buckets appear on chase cards where the listing volume
is enough. Small-population buckets (psa8, bgs9, other) may not surface
until the classifier accumulates more listings."""

# Extra queries to run alongside the raw search, one per graded tier.
# eBay's Browse API sorts by relevance to the query, and a bare "card
# name + number" query returns almost exclusively raw listings — slab
# titles don't rank against raw ones without an explicit grader token.
# So we fan out into (raw query + " PSA 10") style variants to surface
# slabs the raw query wouldn't. Each entry doubles the eBay quota cost
# for chase cards, so keep this list short.
_GRADED_QUERY_SUFFIXES: list[str] = [
    "PSA 10",
]


async def collect_from_ebay(
    ebay: EbayClient,
    card: Card,
    set_: Set | None,
    snapshot_date: str,
) -> list[dict]:
    """Fetch eBay listings for one card, bucket them by grade tier via
    the title classifier, and return one snapshot row per grade bucket
    with at least MIN_LISTINGS_PER_GRADE kept listings.

    Returns [] if no listings survived filtering. On a miss we log a
    compact drop-reason summary so workflow logs are debuggable without
    re-running the inspect script.

    Runs multiple eBay queries per card: one raw-optimized (normal
    sanity ceilings) plus one per entry in `_GRADED_QUERY_SUFFIXES`
    with sanity ceilings disabled (raw ceilings would filter every
    slab as "above_ceiling"). The classifier buckets listings from
    every pass; dedup by URL keeps a cross-query hit from
    double-counting.
    """
    base_query = build_card_query(
        card_name=card.name,
        card_number=card.number,
        printed_total=set_.printed_total if set_ else None,
        set_name=set_.name if set_ else None,
        rarity=card.rarity,
    )

    reference_price = (
        float(card.market_price_usd) if card.market_price_usd is not None else None
    )

    # Raw query: normal sanity ceilings clipping graded slabs.
    detail_raw = await ebay.price_summary_with_trace(
        base_query,
        max_results=50,
        reference_price_usd=reference_price,
        card_number=card.number,
        rarity=card.rarity,
    )

    all_passes = list(detail_raw["passes"])

    # Graded-tier queries: append a grader token so eBay surfaces slab
    # listings, and disable the sanity ceiling so the classifier gets
    # to see them (raw ceilings intentionally clip slab prices).
    for suffix in _GRADED_QUERY_SUFFIXES:
        graded_query = f"{base_query} {suffix}"
        try:
            detail_g = await ebay.price_summary_with_trace(
                graded_query,
                max_results=50,
                reference_price_usd=reference_price,
                card_number=card.number,
                rarity=card.rarity,
                disable_sanity_ceiling=True,
            )
        except Exception as e:
            # Never fail the whole card because a graded pass errored
            # — the raw bucket is the primary product; grade tiles are
            # value-add.
            log.warning(f"{card.id} graded pass ({suffix}) failed: {e}")
            continue
        all_passes.extend(detail_g["passes"])

    # Collect every kept listing (title + price) from all passes; dedup
    # by URL so a slab that surfaces in both raw + graded queries only
    # counts once toward its bucket's median.
    kept: list = []
    seen_urls: set[str] = set()
    for pass_ in all_passes:
        for c in pass_["classifications"]:
            if not c.kept or c.price_usd is None:
                continue
            if c.url:
                if c.url in seen_urls:
                    continue
                seen_urls.add(c.url)
            kept.append(c)

    if not kept:
        # Log the miss with a drop-reason breakdown across ALL passes.
        cls = [c for p in all_passes for c in p["classifications"]]
        drops: dict[str, int] = {}
        for c in cls:
            if not c.kept and c.drop_reason:
                key = c.drop_reason.split(":", 1)[0]
                drops[key] = drops.get(key, 0) + 1
        log.info(
            f"{card.id} ({card.name[:30]}) — no usable listings  "
            f"fetched={len(cls)} kept=0 min_required={detail_raw['min_required']} "
            f"drops={drops}"
        )
        return []

    # Bucket kept listings by classified grade tag.
    buckets: dict[str, list[float]] = {}
    for c in kept:
        grade = classify_grade(c.title)
        buckets.setdefault(grade, []).append(float(c.price_usd))

    rows: list[dict] = []
    now = datetime.utcnow()
    for grade, prices in buckets.items():
        if len(prices) < MIN_LISTINGS_PER_GRADE:
            continue
        prices.sort()
        n = len(prices)
        # Same median definition as the pre-multi-grade summary.
        if n % 2 == 1:
            median_v = prices[n // 2]
        else:
            median_v = (prices[n // 2 - 1] + prices[n // 2]) / 2.0
        rows.append(
            {
                "card_id": card.id,
                "source": SOURCE,
                "variant": VARIANT_ACTIVE,
                "grade": grade,
                "market_price_usd": float(median_v),
                "low_price_usd": float(prices[0]),
                "mid_price_usd": float(median_v),
                "high_price_usd": float(prices[-1]),
                # Browse API returns active listings only — this is the
                # kept-listings count in the grade bucket, not sold count.
                "sales_count": n,
                "snapshot_at": now,
                "snapshot_date": snapshot_date,
            }
        )
    return rows


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
        consecutive_429s = 0
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
                    grade_rows = await collect_from_ebay(ebay, card, card.set, snapshot_date)
                    # collect_from_ebay hits eBay once for the raw pass +
                    # once per _GRADED_QUERY_SUFFIXES entry, so the
                    # per-card cost against --max-calls scales with the
                    # graded-tier fan-out.
                    calls_made += 1 + len(_GRADED_QUERY_SUFFIXES)
                    consecutive_429s = 0
                except EbayClientError as e:
                    errors += 1
                    log.warning(f"{card.id} {card.name!r}: {e}")
                    # Bail out as soon as we see we've burned through the daily
                    # quota — better than grinding through every candidate just
                    # to log 18 identical "too many requests" warnings. Looking
                    # for "429" in the stringified error stays decoupled from
                    # eBay's response shape (status code + structured errorId
                    # are both reflected in EbayClientError.args[0]).
                    if "429" in str(e):
                        consecutive_429s += 1
                        if consecutive_429s >= 3:
                            log.error(
                                "3 consecutive 429s — eBay quota exhausted, "
                                "aborting. Retry after the next PT-midnight "
                                "reset (~16:00 KST)."
                            )
                            break
                    continue
                except Exception as e:
                    errors += 1
                    log.exception(f"{card.id} {card.name!r}: unexpected: {e}")
                    continue

                if not grade_rows:
                    empty_listings += 1
                else:
                    rows_batch.extend(grade_rows)
                    # Compact per-card log line: emit the raw bucket's numbers
                    # (still the most useful one for the "eyeball a card" case)
                    # + a badge showing which grade tiers were captured this
                    # snapshot. Detailed price breakdowns land in the /admin
                    # inspect view.
                    by_grade = {r["grade"]: r for r in grade_rows}
                    tiers = "|".join(sorted(by_grade.keys()))
                    primary = by_grade.get("raw") or grade_rows[0]
                    log.info(
                        f"[{i}/{len(candidates)}] {card.id} {card.name[:40]:40s} "
                        f"[{tiers}] "
                        f"low={primary['low_price_usd']:.2f} "
                        f"median={primary['market_price_usd']:.2f} "
                        f"high={primary['high_price_usd']:.2f}"
                    )

                    # Backfill the denormalized Card.market_price_usd when it's NULL
                    # (so the catalog/grid UI shows a price for sets pokemontcg.io
                    # hasn't synced yet). Never overwrite an existing tcgplayer-derived value.
                    #
                    # For First Partner Illustration sets specifically, prefer the
                    # snapshot's low over its median. In the first weeks after
                    # release, sellers anchor outlier listings 2-4x above the
                    # transactional clearing price to test the market; the median
                    # gets dragged up by those even after the multi-card / sealed
                    # noise filter passes. The low (post-IQR-trim) sits at the
                    # real floor where copies actually clear.
                    #
                    # For the display fallback, prefer the raw bucket — that's
                    # what a browsing user cares about when the catalog is
                    # missing a TCG number. Graded slabs are a different price
                    # story that shouldn't leak into the catalog headline.
                    if card.market_price_usd is None and not dry_run:
                        raw_row = by_grade.get("raw")
                        if raw_row is not None:
                            is_fpic = bool(card.set_id and card.set_id.startswith("fpic-"))
                            display_price = (
                                raw_row["low_price_usd"]
                                if is_fpic
                                else raw_row["market_price_usd"]
                            )
                            await db.execute(
                                update(Card)
                                .where(Card.id == card.id)
                                .where(Card.market_price_usd.is_(None))
                                .values(market_price_usd=display_price)
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
        index_elements=["card_id", "source", "variant", "grade", "snapshot_date"]
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
