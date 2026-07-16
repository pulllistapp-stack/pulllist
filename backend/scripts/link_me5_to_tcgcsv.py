"""Link me5 (Pitch Black) cards to their TCGCSV productIds + do an
initial price snapshot.

Pitch Black cards were seeded manually so they have no
`tcgplayer_product_id`, which means our daily TCGCSV sync (see
`sync_tcgcsv_daily.py`) skips them — that job iterates cards that
already have a productId and refreshes prices, it doesn't discover
new mappings.

This script does the one-shot linking pass:
  1. Fetch TCGCSV group 24688 (ME05: Pitch Black) product list
  2. Filter to card products (those with a Number extended-data field)
  3. Match card numbers to our me5 rows (integer normalize both sides)
  4. Write tcgplayer_product_id + market_price_usd / low / high /
     mid, plus the per-variant `tcgplayer_prices` JSON (Normal,
     Holofoil, Reverse Holofoil sub-types)

After this, `sync_tcgcsv_daily.py` will keep prices refreshed
automatically each night.

Usage:
    python -m scripts.link_me5_to_tcgcsv
    python -m scripts.link_me5_to_tcgcsv --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("link_me5_tcgcsv")


TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
POKEMON_CATEGORY = 3
PITCH_BLACK_GROUP = 24688  # "ME05: Pitch Black"


def _num_int(raw: str | None) -> int | None:
    """Extract the leading integer from a card-number string, but only
    when the string actually STARTS with digits. Rejects promo-style
    "BSP-074" / "SWSH100" / "TG12" prefixes so BSP promos don't
    silently collide with main-set numbers that happen to share the
    trailing digits.

    Handles: "001/084" → 1, "004" → 4, "12/72" → 12
    Rejects:  "BSP-074", "SWSH100", "TG21"       → None"""
    if not raw:
        return None
    m = re.match(r"^\d+", raw)
    return int(m.group(0)) if m else None


async def run(dry_run: bool) -> None:
    await init_db()

    # TCGCSV 401s the default httpx User-Agent as bot-suspicious.
    # A conventional browser UA gets through without any auth.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    }
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        prod_r = await client.get(
            f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/{PITCH_BLACK_GROUP}/products"
        )
        prod_r.raise_for_status()
        products = prod_r.json().get("results", [])

        price_r = await client.get(
            f"{TCGCSV_BASE}/{POKEMON_CATEGORY}/{PITCH_BLACK_GROUP}/prices"
        )
        price_r.raise_for_status()
        prices = price_r.json().get("results", [])

    # Extract cards from products (those with a Number extended field)
    tcg_cards: dict[int, dict] = {}  # num_int → {name, productId, rarity, raw_number}
    for p in products:
        ext = {e["name"]: e["value"] for e in p.get("extendedData", [])}
        raw_num = ext.get("Number")
        num_int = _num_int(raw_num)
        if num_int is None:
            continue
        tcg_cards[num_int] = {
            "productId": p["productId"],
            "name": p["name"],
            "rarity": ext.get("Rarity"),
            "raw_number": raw_num,
        }
    log.info(f"TCGCSV Pitch Black: {len(tcg_cards)} cards with numbers")

    # Group prices by productId (one product can have multiple subTypes)
    prices_by_pid: dict[int, dict[str, dict]] = {}
    for pr in prices:
        pid = pr["productId"]
        sub = pr.get("subTypeName") or "Normal"
        prices_by_pid.setdefault(pid, {})[sub] = pr

    updates_link = 0
    updates_price = 0
    snapshots_written = 0
    unmatched_db = []
    unmatched_tcg = []

    today_iso = date.today().isoformat()
    now_dt = datetime.utcnow()

    async with SessionLocal() as db:
        stmt = select(Card).where(Card.set_id == "me5")
        db_cards = list((await db.execute(stmt)).scalars())
        log.info(f"me5 in DB: {len(db_cards)} cards")

        seen_tcg = set()
        snapshot_rows: list[dict] = []

        for card in db_cards:
            num_int = _num_int(card.number)
            if num_int is None:
                unmatched_db.append(f"{card.id} (no number)")
                continue

            tcg = tcg_cards.get(num_int)
            if not tcg:
                unmatched_db.append(f"{card.id} #{card.number}")
                continue

            seen_tcg.add(num_int)
            pid = tcg["productId"]
            pr_by_sub = prices_by_pid.get(pid, {})

            # Prefer Holofoil > Normal > Reverse Holofoil for the
            # headline market price shown in the card grid; store the
            # full per-subtype dict in tcgplayer_prices JSON.
            #
            # Pre-release chase cards (SIRs, Mega Hyper Rare) often
            # have low/mid/high populated but marketPrice=None — TCGCSV
            # only computes a `market` value once enough sales have
            # cleared. Fall back to midPrice as the headline in that
            # case so the tile shows something useful instead of blank.
            headline_sub = None
            for candidate in ("Holofoil", "Normal", "Reverse Holofoil"):
                p = pr_by_sub.get(candidate)
                if p and (p.get("marketPrice") or p.get("midPrice") or p.get("lowPrice")):
                    headline_sub = candidate
                    break

            headline = pr_by_sub.get(headline_sub) if headline_sub else None
            headline_market = (
                headline.get("marketPrice")
                or headline.get("midPrice")
                or headline.get("lowPrice")
                if headline
                else None
            )

            # Build the tcgplayer_prices JSON in the shape the rest of
            # the app already reads (per-variant low/mid/high/market/
            # directLow).
            pricing_json = {}
            for sub, pr in pr_by_sub.items():
                # Normalize sub-type key to lower-camel that matches
                # the pokemontcg.io shape our UI already renders
                key_map = {
                    "Normal": "normal",
                    "Holofoil": "holofoil",
                    "Reverse Holofoil": "reverseHolofoil",
                    "1st Edition": "1stEdition",
                    "1st Edition Holofoil": "1stEditionHolofoil",
                    "Unlimited": "unlimited",
                    "Unlimited Holofoil": "unlimitedHolofoil",
                }
                key = key_map.get(sub, sub.lower().replace(" ", ""))
                pricing_json[key] = {
                    "low": pr.get("lowPrice"),
                    "mid": pr.get("midPrice"),
                    "high": pr.get("highPrice"),
                    "market": pr.get("marketPrice"),
                    "directLow": pr.get("directLowPrice"),
                }

            n_ascii = "".join(c if ord(c) < 128 else "?" for c in (card.name or ""))
            log.info(
                f"  {card.id:<14} #{card.number or '?':<8} pid={pid} "
                f"headline={headline_sub}={headline.get('marketPrice') if headline else None} "
                f"[{n_ascii[:24]}]"
            )

            if not dry_run:
                card.tcgplayer_product_id = pid
                if headline:
                    card.market_price_usd = headline_market
                    card.low_price_usd = headline.get("lowPrice")
                    card.mid_price_usd = headline.get("midPrice")
                    card.high_price_usd = headline.get("highPrice")
                card.tcgplayer_prices = pricing_json

            updates_link += 1
            if headline and headline_market is not None:
                updates_price += 1
                snapshot_rows.append(
                    {
                        "card_id": card.id,
                        "source": "tcgplayer",
                        "variant": headline_sub.lower().replace(" ", "_"),
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

        # Snapshot insert (upsert on the composite key so re-runs
        # today don't collide with the daily sync writing later)
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
            r = await db.execute(stmt)
            snapshots_written = r.rowcount or 0

        if not dry_run:
            await db.commit()

        # TCG cards with no DB match
        for num_int, tcg in tcg_cards.items():
            if num_int not in seen_tcg:
                unmatched_tcg.append(f"pid={tcg['productId']} #{tcg['raw_number']} {tcg['name'][:40]}")

    log.info("=== summary ===")
    log.info(f"  cards linked (tcgplayer_product_id + prices json): {updates_link}")
    log.info(f"  cards with headline market price set: {updates_price}")
    log.info(f"  price snapshots inserted (source=tcgplayer): {snapshots_written}")
    log.info(f"  db cards with no TCGCSV match: {len(unmatched_db)}")
    for u in unmatched_db[:10]:
        log.info(f"    - {u}")
    log.info(f"  TCGCSV cards with no DB match: {len(unmatched_tcg)}")
    for u in unmatched_tcg[:10]:
        log.info(f"    - {u}")
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
