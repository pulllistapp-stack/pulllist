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

log = logging.getLogger("cleanup_bad_ebay")


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
                Card.name,
                Card.market_price_usd.label("tcg_ref"),
            )
            .join(Card, Card.id == CardPriceSnapshot.card_id)
            .where(CardPriceSnapshot.source == "ebay")
        )
        rows = (await db.execute(stmt)).all()
        log.info(f"Scanning {len(rows)} eBay snapshot rows…")

        to_delete: list[int] = []
        examples: list[tuple[str, float, float, float]] = []  # (card_name, tcg_ref, ebay_price, ratio)
        for r in rows:
            ref = float(r.tcg_ref) if r.tcg_ref is not None else None
            price = float(r.market_price_usd) if r.market_price_usd is not None else None
            if ref is None or ref <= 0 or price is None or price <= 0:
                continue
            ratio = price / ref
            if ratio >= max_ratio:
                to_delete.append(r.id)
                if len(examples) < 15:
                    examples.append((r.name, ref, price, ratio))

        log.info(
            f"Found {len(to_delete)} rows where ebay_price >= {max_ratio}x tcg_ref."
        )
        if examples:
            log.info("Sample offenders:")
            for name, ref, price, ratio in examples:
                log.info(f"  {name[:32]:32s}  tcg={ref:>7.2f}  ebay={price:>9.2f}  ratio={ratio:>6.1f}x")

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
