"""Tighten the stored low/high band on existing TCGplayer snapshot rows.

TCGplayer reports per-variant low / high that include Heavily Played
copies at the bottom and 1st-edition / Mint slab listings at the top —
both pull the chart band wider than the typical raw-NM market.

The sync pipeline now clips low/high at write time (see
`_clip_tcg_band` in sync_tcgplayer_prices.py). This script applies the
same clip retroactively to historical rows so the chart immediately
shows a tight band instead of having to wait days for the trailing
window to drop the pre-clip data.

Usage:
    # Dry-run — count rows that would be tightened, no writes:
    python -m scripts.cleanup_tcgplayer_bands

    # Apply the updates:
    python -m scripts.cleanup_tcgplayer_bands --apply

The clip is idempotent — running it twice is a no-op on the second pass.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot
from scripts.sync_tcgplayer_prices import _clip_tcg_band

log = logging.getLogger("cleanup_tcg_bands")


async def run(apply: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        stmt = (
            select(
                CardPriceSnapshot.id,
                CardPriceSnapshot.market_price_usd,
                CardPriceSnapshot.low_price_usd,
                CardPriceSnapshot.high_price_usd,
                Card.name,
                Card.rarity,
            )
            .join(Card, Card.id == CardPriceSnapshot.card_id)
            .where(CardPriceSnapshot.source == "tcgplayer")
        )
        rows = (await db.execute(stmt)).all()
        log.info(f"Scanning {len(rows)} TCGplayer snapshot rows…")

        changes: list[tuple[int, float | None, float | None]] = []
        examples: list[tuple[str, str, float, float | None, float | None]] = []
        for r in rows:
            market = float(r.market_price_usd) if r.market_price_usd is not None else None
            raw_low = float(r.low_price_usd) if r.low_price_usd is not None else None
            raw_high = float(r.high_price_usd) if r.high_price_usd is not None else None
            new_low, new_high = _clip_tcg_band(market, raw_low, raw_high, r.rarity)

            low_changed = (
                raw_low is not None and new_low is not None and abs(raw_low - new_low) > 0.01
            )
            high_changed = (
                raw_high is not None and new_high is not None and abs(raw_high - new_high) > 0.01
            )
            if not (low_changed or high_changed):
                continue

            changes.append((r.id, new_low, new_high))
            if len(examples) < 15 and market is not None:
                examples.append((r.name, r.rarity or "?", market, raw_high, new_high))

        log.info(f"Found {len(changes)} rows where the clipped band differs from stored.")
        if examples:
            log.info("Sample tightenings (showing high):")
            for name, rarity, market, raw_high, new_high in examples:
                raw_s = f"{raw_high:>9.2f}" if raw_high is not None else "    none"
                new_s = f"{new_high:>9.2f}" if new_high is not None else "    none"
                log.info(
                    f"  {name[:28]:28s}  {rarity[:18]:18s}  market={market:>8.2f}  "
                    f"raw_high={raw_s}  clipped={new_s}"
                )

        if not apply:
            log.info("Dry-run only. Re-run with --apply to write.")
            return
        if not changes:
            log.info("Nothing to update.")
            return

        # Chunked UPDATEs with per-chunk commit — avoids holding a single
        # transaction lock across 100k+ row writes (Render's pg is small).
        # Progress logged every chunk so a long run is observable.
        chunk = 500
        total = 0
        total_changes = len(changes)
        for i in range(0, total_changes, chunk):
            batch = changes[i : i + chunk]
            for snap_id, new_low, new_high in batch:
                await db.execute(
                    update(CardPriceSnapshot)
                    .where(CardPriceSnapshot.id == snap_id)
                    .values(low_price_usd=new_low, high_price_usd=new_high)
                )
                total += 1
            await db.commit()
            log.info(f"  Committed chunk: {total}/{total_changes} rows updated")
        log.info(f"Done — updated {total} rows total.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write updates. Without this flag the script only reports.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
