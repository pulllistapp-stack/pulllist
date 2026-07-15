"""Use each DECK set's sealed product image as the set logo.

LO's ask: for DECK-type sets (starter decks, build boxes, preconstructed
decks, trainer boxes), the current Limitless set logo shows the parent
expansion mark — useless for identifying a specific product. The actual
box photo is what the tile should show, matching how e-commerce sites
(TCG Republic, eBay) surface these products.

We already have TCGCSV product images on the sealed side (loaded by
``ingest_jp_sealed``). This script copies the first sealed product's
image_url onto the set's logo_url, upgrading the 200w thumbnail path
to _400w for a crisper set tile.

Scope: JP language, set_type='DECK', at least one sealed product with
an image_url. Non-DECK sets (MAIN expansions, PROMO_NEW/LEGACY) keep
their existing Limitless logos — those actually do represent the
release properly.

Idempotent — re-runs UPDATE the URL only if the derived value differs.

Usage:
    python -m scripts.backfill_deck_logos_from_sealed --dry-run
    python -m scripts.backfill_deck_logos_from_sealed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("backfill_deck_logos_from_sealed")


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # For each JP DECK set, pick the smallest tcgplayer_product_id
        # of a sealed product with a non-null image. Smallest id ≈
        # earliest TCGCSV entry, which is usually the primary
        # (base-price) SKU — deluxe/variant boxes get later ids.
        rows = (await db.execute(text("""
            SELECT DISTINCT ON (s.id)
                s.id AS set_id,
                s.logo_url AS current_logo,
                p.image_url AS product_image
            FROM sets s
            JOIN products p ON p.set_id = s.id
            WHERE s.language = 'ja'
              AND s.set_type = 'DECK'
              AND p.image_url IS NOT NULL
            ORDER BY s.id, p.tcgplayer_product_id ASC
        """))).all()

    log.info(f"DECK sets with a sealed image available: {len(rows)}")

    stats = {"scanned": len(rows), "updated": 0, "unchanged": 0}
    async with SessionLocal() as db:
        for r in rows:
            # TCGCSV serves _200w and _400w — swap in the larger for
            # a crisper set-browser tile. _500w+ 403s on tcgplayer-cdn,
            # so 400w is the ceiling.
            desired = (r.product_image or "").replace("_200w", "_400w")
            if not desired:
                continue
            if r.current_logo == desired:
                stats["unchanged"] += 1
                continue

            if dry_run:
                stats["updated"] += 1
                log.info(f"  [would] {r.set_id} → {desired}")
                continue

            await db.execute(
                text("UPDATE sets SET logo_url = :u WHERE id = :i"),
                {"u": desired, "i": r.set_id},
            )
            stats["updated"] += 1

        if not dry_run:
            await db.commit()

    log.info("=== DECK logo backfill from sealed ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry_run:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
