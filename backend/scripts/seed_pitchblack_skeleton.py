"""Seed the Pitch Black (ME5) EN set as a skeleton.

Why a skeleton and not the usual TCGCSV pull:
    TCGCSV's ME05 group (24688) currently exposes sealed products
    only (Booster Boxes, ETBs, blisters) — individual cards will not
    be indexed until closer to the July 17 launch. pokemontcg.io,
    Limitless, TCGdex all lag behind too.

    We DO know the set shape from pokemon.com — their public CDN at
    dz3we2x72f7ol.cloudfront.net/expansions/pitch-black/en-us/KD5B_EN_
    hosts pre-release marketing images (a pink placeholder tile with
    the filename baked in — verified 2026-07-05). Main set enumerates
    1..120 and BSP variants sit at 74/75/76/77/82/83/84/85. That's
    enough to seed a card-per-row skeleton with placeholder names,
    even though we can't reuse the CDN image (it's not real art).

    Card art fills in later:
      - image_small / image_large stay NULL. The CardThumb component
        falls back to a stylised name-in-frame placeholder that reads
        far better than the pokemon.com pink template.
      - Once TCGCSV starts indexing individual products (typically
        1-2 weeks post-launch), sync_tcgcsv_daily upserts real image
        URLs (from tcgplayer-cdn.tcgplayer.com) plus name / rarity /
        tcgplayer_product_id / prices. The skeleton id pattern
        (me5-NNN) matches what seed_promo_group derives from the
        TCGplayer product names, so the upserts are lossless.

    Card_id id pattern:
        me5-001..me5-120         (main set)
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
            # image_small / image_large intentionally NULL — the
            # pokemon.com CDN only serves a pre-release pink
            # placeholder here (verified 2026-07-05). Leaving these
            # null lets CardThumb draw its own stylised name
            # placeholder instead, and daily sync patches the real
            # TCGplayer CDN URL in as soon as TCGCSV indexes the card.
            img = None
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
