"""Seed the Pitch Black (ME5) EN set as a skeleton.

Why a skeleton and not the usual TCGCSV pull:
    TCGCSV's ME05 group (24688) currently exposes sealed products
    only (Booster Boxes, ETBs, blisters) — individual cards will not
    be indexed until closer to the July 17 launch. pokemontcg.io,
    Limitless, TCGdex all lag behind too.

    Meanwhile pokemon.com's public CDN already hosts every card image
    at a deterministic URL:
        https://dz3we2x72f7ol.cloudfront.net/expansions/pitch-black/
        en-us/KD5B_EN_{NNN}.png
    Main set: KD5B_EN_1..120 (120 cards, no gaps).
    Black Star Promos: KD5B_BSP_EN_74..85 (8 cards, sparse).

    This script seeds 120 + 8 = 128 skeleton cards using those image
    URLs, with a placeholder "Pitch Black #NNN" name. When TCGCSV
    starts indexing individual products (typically 1-2 weeks post-
    launch), our existing sync_tcgcsv_daily overwrites name / rarity
    / tcgplayer_product_id / prices in place — the skeleton id
    pattern (me5-NNN) matches what seed_promo_group would derive from
    the TCGplayer product name, so upserts are lossless.

    Card_id id pattern:
        me5-001..me5-120        (main set)
        me5-bsp-074..me5-bsp-085 (Black Star Promo variants)

Idempotent — re-runs skip cards already in the DB.

Run:
    python -m scripts.seed_pitchblack_skeleton
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Card, Set  # noqa: E402


log = logging.getLogger("seed_pitchblack_skeleton")


CDN = "https://dz3we2x72f7ol.cloudfront.net/expansions/pitch-black/en-us"

SET_ID = "me5"
SET_NAME = "Pitch Black"
SET_SERIES = "Mega Evolution"
SET_RELEASE = date(2026, 7, 17)

# From our CDN enumeration:
MAIN_RANGE = range(1, 121)                # 120 cards, no gaps
BSP_NUMBERS = [74, 75, 76, 77, 82, 83, 84, 85]  # sparse — CDN 404s the gap


async def main() -> None:
    await init_db()
    stats = {
        "set_created": False,
        "main_inserted": 0,
        "main_skipped": 0,
        "bsp_inserted": 0,
        "bsp_skipped": 0,
    }

    async with SessionLocal() as db:
        # ── Set upsert ──────────────────────────────────────────────
        existing_set = await db.get(Set, SET_ID)
        if existing_set is None:
            db.add(
                Set(
                    id=SET_ID,
                    name=SET_NAME,
                    series=SET_SERIES,
                    release_date=SET_RELEASE,
                    language="en",
                    printed_total=len(list(MAIN_RANGE)),
                    total=len(list(MAIN_RANGE)) + len(BSP_NUMBERS),
                )
            )
            await db.commit()
            stats["set_created"] = True
            log.info("Created Set %s (%s)", SET_ID, SET_NAME)
        else:
            log.info("Set %s already exists; skipping create", SET_ID)

        # ── Main set cards ──────────────────────────────────────────
        for n in MAIN_RANGE:
            card_id = f"{SET_ID}-{n:03d}"
            if await db.get(Card, card_id) is not None:
                stats["main_skipped"] += 1
                continue
            # Only one image size exposed on this CDN — reuse for both
            # small and large slots so thumbnails and detail views can
            # both render. next/image will re-size on the fly.
            img = f"{CDN}/KD5B_EN_{n}.png"
            db.add(
                Card(
                    id=card_id,
                    name=f"Pitch Black #{n:03d}",
                    supertype=None,  # unknown until TCGCSV catches up
                    rarity=None,
                    number=f"{n:03d}",
                    number_int=n,
                    image_small=img,
                    image_large=img,
                    set_id=SET_ID,
                    language="en",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            stats["main_inserted"] += 1

        # ── Black Star Promo variants ───────────────────────────────
        for n in BSP_NUMBERS:
            card_id = f"{SET_ID}-bsp-{n:03d}"
            if await db.get(Card, card_id) is not None:
                stats["bsp_skipped"] += 1
                continue
            img = f"{CDN}/KD5B_BSP_EN_{n}.png"
            db.add(
                Card(
                    id=card_id,
                    name=f"Pitch Black BSP #{n:03d}",
                    supertype=None,
                    rarity="Promo",
                    number=f"BSP-{n:03d}",
                    number_int=n,
                    image_small=img,
                    image_large=img,
                    set_id=SET_ID,
                    language="en",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            stats["bsp_inserted"] += 1

        await db.commit()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %s: %s", k, v)


if __name__ == "__main__":
    asyncio.run(main())
