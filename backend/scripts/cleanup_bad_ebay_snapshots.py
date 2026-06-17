"""Wipe eBay snapshot rows whose price is implausible vs the card's TCGplayer
market reference.

Background — the snapshot pipeline now applies a sanity band
(0.30x..5.0x of TCG market, with sensible absolutes), but historical rows
collected before that guard, OR rows collected for cards whose
Card.market_price_usd was NULL at write-time, can be 100-300x off (e.g.
Pikachu Legendary Collection #86 stored at $599 when the base print is
$1.91 — the eBay search caught the reverse-holo parallel).

This script finds those rows and deletes them.

Usage:
    # Dry-run (default) — counts only, no writes:
    python -m scripts.cleanup_bad_ebay_snapshots

    # Real run:
    python -m scripts.cleanup_bad_ebay_snapshots --apply

    # Tighter or looser tolerance (default 10x):
    python -m scripts.cleanup_bad_ebay_snapshots --max-ratio 8.0 --apply
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_, delete, select

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot
from app.services.ebay_client import _DEFAULT_ABS_CEILING, _RARITY_ABS_CEILING

log = logging.getLogger("cleanup_bad_ebay")


def _rarity_ceiling(rarity: str | None) -> float:
    """Mirror the live filter's rarity-based absolute ceiling so cleanup
    catches no-TCG-ref pollution (vintage Pokemon ⭐ Stars, Legendary
    Collection reverse-holos, etc.) that the ratio check skips."""
    if rarity and rarity in _RARITY_ABS_CEILING:
        return _RARITY_ABS_CEILING[rarity]
    return _DEFAULT_ABS_CEILING


async def run(max_ratio: float, apply: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # Pull every eBay snapshot joined with its card's current TCG ref.
        # Friends-beta scale (~10k cards × handful of days) fits in memory.
        stmt = (
            select(
                CardPriceSnapshot.id,
                CardPriceSnapshot.card_id,
                CardPriceSnapshot.market_price_usd,
                CardPriceSnapshot.high_price_usd,
                Card.name,
                Card.rarity,
                Card.market_price_usd.label("tcg_ref"),
            )
            .join(Card, Card.id == CardPriceSnapshot.card_id)
            .where(CardPriceSnapshot.source == "ebay")
        )
        rows = (await db.execute(stmt)).all()
        log.info(f"Scanning {len(rows)} eBay snapshot rows…")

        to_delete: list[int] = []
        examples: list[tuple[str, str, float | None, float, float, str]] = []
        for r in rows:
            ref = float(r.tcg_ref) if r.tcg_ref is not None else None
            price = float(r.market_price_usd) if r.market_price_usd is not None else None
            high = float(r.high_price_usd) if r.high_price_usd is not None else None

            # Mirrors the live filter: rarity ceiling always applies, and
            # when TCG ref is present we also run the 10x ratio check.
            # Either gate firing = delete.
            qualifies = False
            via = ""

            if ref is not None and ref > 0:
                median_ratio = (price / ref) if (price and price > 0) else 0
                high_ratio = (high / ref) if (high and high > 0) else 0
                worst_ratio = max(median_ratio, high_ratio)
                if worst_ratio >= max_ratio:
                    qualifies = True
                    via = "median" if median_ratio >= high_ratio else "high"

            if not qualifies:
                ceiling = _rarity_ceiling(r.rarity)
                if (price and price > ceiling) or (high and high > ceiling):
                    qualifies = True
                    via = "ceiling"

            if qualifies:
                to_delete.append(r.id)
                if len(examples) < 15:
                    examples.append((r.name, r.rarity or "?", ref, price or 0, high or 0, via))

        log.info(
            f"Found {len(to_delete)} rows that fail ratio (>={max_ratio}x) "
            f"or rarity-ceiling check."
        )
        if examples:
            log.info("Sample offenders:")
            for name, rarity, ref, price, high, via in examples:
                tcg = f"{ref:>7.2f}" if ref is not None else "   none"
                log.info(
                    f"  {name[:28]:28s}  {rarity[:18]:18s}  tcg={tcg}  "
                    f"median={price:>8.2f}  high={high:>9.2f}  via={via}"
                )

        if not apply:
            log.info("Dry-run only. Re-run with --apply to delete.")
            return

        if not to_delete:
            log.info("Nothing to delete.")
            return

        # Chunked delete so we don't blow out the parameter limit on Postgres.
        chunk = 500
        total = 0
        for i in range(0, len(to_delete), chunk):
            ids = to_delete[i : i + chunk]
            stmt = delete(CardPriceSnapshot).where(CardPriceSnapshot.id.in_(ids))
            res = await db.execute(stmt)
            total += res.rowcount or 0
        await db.commit()
        log.info(f"Deleted {total} rows.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-ratio", type=float, default=10.0,
        help="Delete eBay rows where market_price >= this multiple of card's TCG ref (default 10.0)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually delete. Without this flag the script only reports.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run(max_ratio=args.max_ratio, apply=args.apply))


if __name__ == "__main__":
    main()
