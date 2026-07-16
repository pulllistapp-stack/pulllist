"""Link me30 Classic Collection (CC01-CC11) card artwork to the
originals they reprint.

Classic Collection cards in the 30th Celebration set are literal
reprints of iconic cards from Pokémon TCG history with a fresh foil
treatment. Instead of scraping new artwork for the 30th version, we
just point each me30-cc-NN row at the original card's image_small /
image_large — same illustration, same collector recognition, zero
new asset hosting.

Mapping is hand-curated because the "correct" original for cards
with many printings (Pikachu, Charizard, Zacian V, Arceus VSTAR)
is a judgment call. When the official 30th checklist ships with
canonical print numbers we can refine this map.

Usage:
    python -m scripts.link_me30_classic_to_originals
    python -m scripts.link_me30_classic_to_originals --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Card


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("link_me30_classic")


# Hand-picked source card ids for each Classic Collection slot.
# Picked to match the OG "iconic" printing for each card:
#   * Base Set cards go to base1 (the 1999 shadowless-era originals)
#   * Full Art V's use full-art print (swsh1-195 vs base swsh1-138)
#   * VSTAR use alt art (swsh9-184 vs base swsh9-123)
#   * LEGENDs are top/bottom halves — hgss4-99 and hgss4-100 pair up
#   * Vivid Voltage Amazing Rare Raikou is the specific referenced print
CLASSIC_MAP: dict[str, str] = {
    "me30-cc-01": "base1-4",     # Charizard — Base Set (1999)
    "me30-cc-02": "base1-58",    # Pikachu — Base Set
    "me30-cc-03": "dp4-106",     # Palkia LV.X — Great Encounters
    "me30-cc-04": "dp6-43",      # Uxie — Legends Awakened
    "me30-cc-05": "ecard2-149",  # Lugia — Aquapolis (Crystal)
    "me30-cc-06": "hgss4-99",    # Darkrai & Cresselia LEGEND (top) — Triumphant
    "me30-cc-07": "hgss4-100",   # Darkrai & Cresselia LEGEND (bottom) — Triumphant
    "me30-cc-08": "sm9-162",     # Pikachu & Zekrom-GX SIR — Team Up
    "me30-cc-09": "swsh1-195",   # Zacian V (Full Art) — Sword & Shield
    "me30-cc-10": "swsh4-50",    # Raikou (Amazing Rare) — Vivid Voltage
    "me30-cc-11": "swsh9-184",   # Arceus VSTAR (Alt Art) — Brilliant Stars
}


async def run(dry_run: bool) -> None:
    await init_db()

    updates = 0
    skipped = 0
    errors = []

    async with SessionLocal() as db:
        for cc_id, source_id in CLASSIC_MAP.items():
            src = await db.get(Card, source_id)
            if not src:
                errors.append(f"source missing: {source_id} (for {cc_id})")
                continue
            if not src.image_small:
                errors.append(f"source has no image: {source_id} (for {cc_id})")
                continue

            cc = await db.get(Card, cc_id)
            if not cc:
                errors.append(f"CC card missing: {cc_id}")
                continue

            if cc.image_small and cc.image_large:
                skipped += 1
                log.info(f"  {cc_id}: already has image, skipped")
                continue

            log.info(
                f"  {cc_id} ({cc.name}) ← {source_id} ({src.name})"
            )
            if not dry_run:
                cc.image_small = src.image_small
                cc.image_large = src.image_large
            updates += 1

        if not dry_run:
            await db.commit()

    log.info("=== summary ===")
    log.info(f"  linked: {updates}")
    log.info(f"  skipped (already had image): {skipped}")
    log.info(f"  errors: {len(errors)}")
    for e in errors:
        log.info(f"    - {e}")
    log.info(f"  dry_run: {dry_run}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
