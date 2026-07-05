"""Seed ME: 30th Celebration (me30) from TCGCSV group 24722.

Situation as of the seed:
    TCGCSV is progressively indexing individual cards ahead of the
    2026-09-16 launch. Right now group 24722 exposes ~53 products —
    a mix of:
      - Fully-numbered cards: 'Pikachu - 036/128'  ← seed cleanly
      - Named but pre-numbering: 'Greninja ex'     ← wait for later
      - Sealed products: 'Booster Bundle', 'ETB', 'Tin', 'Blister',
        'Collection', 'Sticker', 'Binder', 'Pack Case'
        ← ALWAYS skip; not cards

    seed_promo_group.py's parser mishandles the sealed items — it
    latches onto the '2' in 'Set of 2' and misfiles a booster bundle
    as card #002. That's the reason this set gets its own seeder
    instead of reusing the generic one.

Re-run this script as launch approaches (weekly is fine): every run
picks up whatever TCGCSV has newly numbered. The upsert is keyed on
card_id (me30-NNN), so re-runs are idempotent and never overwrite a
card that's already fully filled in.

Run:
    python -m scripts.seed_30thcelebration
    python -m scripts.seed_30thcelebration --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Card, Set  # noqa: E402


log = logging.getLogger("seed_30thcelebration")


TCGCSV = "https://tcgcsv.com/tcgplayer/3/24722/products"
USER_AGENT = "PullList/1.0 (https://pulllist.org; bot)"

SET_ID = "me30"
# LO's preference: drop the "ME:" era prefix on the set browse page —
# users think of it as "30th Celebration" or "30th Anniversary".
SET_NAME = "30th Celebration"
SET_SERIES = "Mega Evolution"
SET_RELEASE = date(2026, 9, 16)
# Official pokemon.com wordmark logo. We briefly tried swapping this
# for a pokecottage card collage but LO wanted the original logo
# preserved — the actual card art from that scrape ended up going
# into individual MEP-107..110 rows (Pikachu ex, Espeon ex, Umbreon
# ex — the 30th anniversary is releasing them as MEP promos, not a
# me30 expansion).
SET_LOGO = (
    "https://d1i787aglh9bmb.cloudfront.net/assets/img/global/logos/en-us/thirty.png"
)

# Anything with these substrings is a sealed product, not a card. Keeps
# a booster bundle from being seeded as me30-002 just because '2' shows
# up in "Set of 2".
_SEALED_KEYWORDS = re.compile(
    r"\b("
    r"booster|elite trainer box|etb|bundle|blister|tin|"
    r"collection|sticker|binder|poster|"
    r"pack case|box case|packs case|display case|"
    r"knock out|premium|mini tin"
    r")\b",
    re.IGNORECASE,
)

# 'Pikachu - 036/128' → number 036. Requires the slash-separator form
# so we don't confuse a stray digit in a marketing string for a card
# number.
_NUMBER_RE = re.compile(r"\s-\s(\d{1,3})/\d{1,3}\s*$")


def _looks_sealed(name: str) -> bool:
    return bool(_SEALED_KEYWORDS.search(name))


def _extract_number(name: str) -> tuple[str, str] | tuple[None, None]:
    """Return (clean_name, number) or (None, None) if no NNN/TTT tail."""
    m = _NUMBER_RE.search(name)
    if not m:
        return None, None
    num = m.group(1).zfill(3)
    clean = _NUMBER_RE.sub("", name).strip()
    return clean, num


async def _fetch_products() -> list[dict]:
    async with httpx.AsyncClient(
        timeout=60.0, headers={"User-Agent": USER_AGENT}
    ) as c:
        r = await c.get(TCGCSV)
        r.raise_for_status()
        return r.json().get("results", [])


async def main(dry_run: bool) -> None:
    await init_db()
    products = await _fetch_products()
    log.info("fetched %d products from TCGCSV group 24722", len(products))

    stats = {
        "sealed_skipped": 0,
        "unnumbered_skipped": 0,
        "cards_inserted": 0,
        "cards_updated": 0,
    }

    async with SessionLocal() as db:
        # ── Set upsert ──────────────────────────────────────────────
        existing = await db.get(Set, SET_ID)
        if existing is None:
            if not dry_run:
                db.add(
                    Set(
                        id=SET_ID,
                        name=SET_NAME,
                        series=SET_SERIES,
                        release_date=SET_RELEASE,
                        language="en",
                        printed_total=128,
                        total=128,
                        logo_url=SET_LOGO,
                    )
                )
                await db.commit()
            log.info("created Set %s", SET_ID)
        else:
            log.info("Set %s already exists; cards upsert only", SET_ID)
            if existing.logo_url != SET_LOGO and not dry_run:
                existing.logo_url = SET_LOGO
                await db.commit()

        # ── Cards ───────────────────────────────────────────────────
        for p in products:
            raw = p.get("name", "")
            if _looks_sealed(raw):
                stats["sealed_skipped"] += 1
                continue
            clean, num = _extract_number(raw)
            if num is None:
                stats["unnumbered_skipped"] += 1
                log.info("  wait for numbering: %s", raw)
                continue

            card_id = f"{SET_ID}-{num}"
            image_url = p.get("imageUrl")
            image_small = image_url
            image_large = (
                image_url.replace("_200w.jpg", "_400w.jpg") if image_url else None
            )

            existing_card = await db.get(Card, card_id)
            if existing_card is None:
                if not dry_run:
                    db.add(
                        Card(
                            id=card_id,
                            name=clean,
                            supertype=None,
                            rarity=None,
                            number=num,
                            number_int=int(num),
                            image_small=image_small,
                            image_large=image_large,
                            tcgplayer_url=p.get("url"),
                            tcgplayer_product_id=p.get("productId"),
                            set_id=SET_ID,
                            language="en",
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                    )
                stats["cards_inserted"] += 1
                log.info("  + %s  %s  (productId=%s)", card_id, clean, p.get("productId"))
            else:
                if not dry_run:
                    existing_card.name = clean
                    existing_card.image_small = image_small
                    existing_card.image_large = image_large
                    existing_card.tcgplayer_url = p.get("url")
                    existing_card.tcgplayer_product_id = p.get("productId")
                    existing_card.updated_at = datetime.utcnow()
                stats["cards_updated"] += 1

        if not dry_run:
            await db.commit()

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %s: %s", k, v)
    log.info("  dry_run: %s", dry_run)


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.dry_run))


if __name__ == "__main__":
    cli()
