"""Seed the 8 real Pitch Black-associated promo cards from the MEP
(Mega Evolution Promo) TCGCSV group.

Background: me5 had 8 placeholder rows (me5-bsp-074 through me5-
bsp-085) with generic names like "Pitch Black BSP #074" and no
images or prices. Those placeholders were wrong — numbers 074-077
in TCGCSV's MEP group are actually earlier ME1-ME4 promos
(Delphox, Ampharos, Crobat, Goodra), not Pitch Black anything.

The real Pitch Black promos live at MEP #082-088 (8 physical cards
total, one of them has a Pokemon Center variant sharing #088):

  #082 Miraidon           — Prerelease stamped / Build & Battle Box
  #083 Slowbro            — Prerelease stamped / Build & Battle Box
  #084 Dhelmise           — Prerelease stamped / Build & Battle Box
  #085 Bastiodon          — Prerelease stamped / Build & Battle Box
  #086 Slowpoke (Cosmos)  — Blister exclusive
  #087 Binacle (Cosmos)   — Blister exclusive
  #088 Zarude             — Store gift-with-purchase (GameStop / EB Games)
  #088 Zarude (PC)        — Pokemon Center exclusive

This script:
  1. Deletes the 8 stale me5-bsp-XXX placeholder rows
  2. Creates 8 new rows (me5-bsp-082 through me5-bsp-088 + one
     -pkc variant) with the actual TCGCSV product data
  3. Wraps tcgplayer image URLs through the weserv proxy per
     project convention

Same TCGCSV bootstrap pattern as link_me5_to_tcgcsv.py — fetches
products + prices for the MEP group, then match by hardcoded
productIds.

Usage:
    python -m scripts.seed_me5_promos
    python -m scripts.seed_me5_promos --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import urllib.parse
from datetime import date, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("seed_me5_promos")


TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
POKEMON_CATEGORY = 3
MEP_GROUP = 24451  # "ME: Mega Evolution Promo"

# Mapping from our target card_id → TCGCSV productId. Hand-picked
# after inspecting the MEP #074-088 range and identifying the
# Pitch Black-specific promos.
PITCH_BLACK_PROMOS: list[dict] = [
    {"card_id": "me5-bsp-082", "product_id": 706135, "number": "082",
     "name": "Miraidon", "display_name": "Miraidon (Pitch Black Stamped)"},
    {"card_id": "me5-bsp-083", "product_id": 706129, "number": "083",
     "name": "Slowbro", "display_name": "Slowbro (Pitch Black Stamped)"},
    {"card_id": "me5-bsp-084", "product_id": 706137, "number": "084",
     "name": "Dhelmise", "display_name": "Dhelmise (Pitch Black Stamped)"},
    {"card_id": "me5-bsp-085", "product_id": 706133, "number": "085",
     "name": "Bastiodon", "display_name": "Bastiodon (Pitch Black Stamped)"},
    {"card_id": "me5-bsp-086", "product_id": 706130, "number": "086",
     "name": "Slowpoke", "display_name": "Slowpoke (Cosmos Holo)"},
    {"card_id": "me5-bsp-087", "product_id": 706131, "number": "087",
     "name": "Binacle", "display_name": "Binacle (Cosmos Holo)"},
    {"card_id": "me5-bsp-088", "product_id": 706193, "number": "088",
     "name": "Zarude", "display_name": "Zarude (ETB Promo)"},
    {"card_id": "me5-bsp-088-pkc", "product_id": 706199, "number": "088",
     "name": "Zarude", "display_name": "Zarude (Pokémon Center Exclusive)"},
]


def _weserv_wrap(url: str) -> str:
    return (
        "https://images.weserv.nl/?url="
        + urllib.parse.quote(url, safe="")
        + "&output=webp"
    )


async def run(dry_run: bool) -> None:
    await init_db()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    }
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        prod_r = await client.get(
            f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/{MEP_GROUP}/products"
        )
        prod_r.raise_for_status()
        products = {p["productId"]: p for p in prod_r.json().get("results", [])}

        price_r = await client.get(
            f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/{MEP_GROUP}/prices"
        )
        price_r.raise_for_status()
        prices_by_pid: dict[int, dict[str, dict]] = {}
        for pr in price_r.json().get("results", []):
            prices_by_pid.setdefault(pr["productId"], {})[
                pr.get("subTypeName") or "Normal"
            ] = pr

    today_iso = date.today().isoformat()
    now_dt = datetime.utcnow()

    async with SessionLocal() as db:
        # Step 1: drop the stale placeholders
        stale = await db.execute(
            select(Card).where(
                Card.set_id == "me5",
                Card.id.like("me5-bsp-%"),
            )
        )
        stale_ids = [c.id for c in stale.scalars()]
        log.info(f"deleting {len(stale_ids)} stale me5-bsp-* placeholder rows")
        if stale_ids and not dry_run:
            await db.execute(
                delete(Card).where(Card.id.in_(stale_ids))
            )

        snapshot_rows: list[dict] = []

        for spec in PITCH_BLACK_PROMOS:
            pid = spec["product_id"]
            product = products.get(pid)
            if not product:
                log.warning(f"  product {pid} missing from MEP TCGCSV")
                continue

            # Direct TCGplayer CDN URL matches the pattern the existing
            # mep set already uses (mep-034 etc.). weserv proxy rejects
            # tcgplayer.com with "Domain or TLD blocked by policy" so
            # we don't wrap this source — the direct URL loads fine in
            # browsers because TCGplayer allows hot-linking.
            #
            # imageCount==0 signals TCGCSV knows the URL pattern but
            # TCGplayer hasn't uploaded the actual JPEG yet (brand-new
            # promos, days after seeding). Store None so the tile
            # renders the "no image" placeholder instead of a broken
            # image icon; a re-run in a few days will pick up the
            # image once TCGplayer catches up.
            image_url = (
                product.get("imageUrl")
                or f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_200w.jpg"
            )
            if product.get("imageCount", 0) < 1:
                image_url = None

            pr_by_sub = prices_by_pid.get(pid, {})
            # Promos are usually single-sub-type; take whichever exists
            headline = None
            for sub in ("Holofoil", "Normal", "Reverse Holofoil"):
                if sub in pr_by_sub:
                    headline = pr_by_sub[sub]
                    break
            if headline is None and pr_by_sub:
                headline = next(iter(pr_by_sub.values()))

            headline_market = (
                headline.get("marketPrice")
                or headline.get("midPrice")
                or headline.get("lowPrice")
                if headline
                else None
            )

            pricing_json = {}
            for sub, pr in pr_by_sub.items():
                key_map = {
                    "Normal": "normal",
                    "Holofoil": "holofoil",
                    "Reverse Holofoil": "reverseHolofoil",
                }
                key = key_map.get(sub, sub.lower().replace(" ", ""))
                pricing_json[key] = {
                    "low": pr.get("lowPrice"),
                    "mid": pr.get("midPrice"),
                    "high": pr.get("highPrice"),
                    "market": pr.get("marketPrice"),
                    "directLow": pr.get("directLowPrice"),
                }

            new_card = Card(
                id=spec["card_id"],
                name=spec["display_name"],
                number=spec["number"],
                supertype="Pokémon" if spec["name"] not in ("Zarude",) else "Pokémon",
                rarity="Promo",
                image_small=image_url,
                image_large=image_url,
                set_id="me5",
                language="en",
                tcgplayer_product_id=pid,
                tcgplayer_prices=pricing_json,
                market_price_usd=headline_market,
                low_price_usd=headline.get("lowPrice") if headline else None,
                mid_price_usd=headline.get("midPrice") if headline else None,
                high_price_usd=headline.get("highPrice") if headline else None,
            )
            log.info(
                f"  {spec['card_id']:<20} pid={pid} "
                f"${headline_market or 0:>7.2f}  {spec['display_name']}"
            )
            if not dry_run:
                db.add(new_card)

            if headline_market is not None:
                snapshot_rows.append(
                    {
                        "card_id": spec["card_id"],
                        "source": "tcgplayer",
                        "variant": "active",
                        "grade": "raw",
                        "market_price_usd": headline_market,
                        "low_price_usd": headline.get("lowPrice"),
                        "mid_price_usd": headline.get("midPrice"),
                        "high_price_usd": headline.get("highPrice"),
                        "sales_count": None,
                        "snapshot_at": now_dt,
                        "snapshot_date": today_iso,
                    }
                )

        if not dry_run:
            await db.flush()

        if not dry_run and snapshot_rows:
            dialect = db.bind.dialect.name
            ins_cls = pg_insert if dialect == "postgresql" else sqlite_insert
            stmt = ins_cls(CardPriceSnapshot).values(snapshot_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    "card_id", "source", "variant", "grade", "snapshot_date"
                ],
                set_={
                    "market_price_usd": stmt.excluded.market_price_usd,
                    "low_price_usd": stmt.excluded.low_price_usd,
                    "mid_price_usd": stmt.excluded.mid_price_usd,
                    "high_price_usd": stmt.excluded.high_price_usd,
                    "snapshot_at": stmt.excluded.snapshot_at,
                },
            )
            await db.execute(stmt)

        if not dry_run:
            await db.commit()

    log.info("=== summary ===")
    log.info(f"  stale placeholders deleted: {len(stale_ids)}")
    log.info(f"  Pitch Black promos seeded: {len(PITCH_BLACK_PROMOS)}")
    log.info(f"  price snapshots inserted: {len(snapshot_rows)}")
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
