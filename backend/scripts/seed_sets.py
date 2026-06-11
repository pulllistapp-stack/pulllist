"""
Seed all Pokémon TCG sets + cards from pokemontcg.io into local DB.

Usage:
    python -m scripts.seed_sets              # seed all sets, skip existing
    python -m scripts.seed_sets --refresh    # re-fetch even if present
    python -m scripts.seed_sets --set sv8    # seed a single set by id
    python -m scripts.seed_sets --sets-only  # skip card details (faster)
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import date, datetime
from pathlib import Path

_NUMBER_PREFIX = re.compile(r"^(\d+)")


def parse_card_number(value: str | None) -> int | None:
    if not value:
        return None
    m = _NUMBER_PREFIX.match(value)
    return int(m.group(1)) if m else None


def parse_hp(value: str | None) -> int | None:
    if not value:
        return None
    m = _NUMBER_PREFIX.match(value)
    return int(m.group(1)) if m else None

# Make `app.*` imports work whether run as module or script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Card, Set

POKEMONTCG_BASE = "https://api.pokemontcg.io/v2"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/json"}
    if settings.pokemontcg_api_key:
        h["X-Api-Key"] = settings.pokemontcg_api_key
    return h


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _market_price_from_tcgplayer(prices: dict | None) -> float | None:
    if not prices:
        return None
    best: float | None = None
    for variant in prices.values():
        if not isinstance(variant, dict):
            continue
        market = variant.get("market") or variant.get("mid")
        if isinstance(market, (int, float)):
            if best is None or market > best:
                best = float(market)
    return best


async def fetch_all_sets(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{POKEMONTCG_BASE}/sets", headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


async def fetch_cards_for_set(client: httpx.AsyncClient, set_id: str) -> list[dict]:
    all_cards: list[dict] = []
    page = 1
    while True:
        resp = await client.get(
            f"{POKEMONTCG_BASE}/cards",
            headers=_headers(),
            params={"q": f"set.id:{set_id}", "page": page, "pageSize": 250},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data", [])
        all_cards.extend(data)
        if len(data) < 250:
            break
        page += 1
    return all_cards


async def upsert_set(db, raw: dict) -> Set:
    images = raw.get("images", {}) or {}
    set_row = await db.get(Set, raw["id"])
    if set_row is None:
        set_row = Set(id=raw["id"])
        db.add(set_row)
    set_row.name = raw.get("name", "")
    set_row.series = raw.get("series")
    set_row.printed_total = raw.get("printedTotal")
    set_row.total = raw.get("total")
    set_row.ptcgo_code = raw.get("ptcgoCode")
    set_row.release_date = _parse_date(raw.get("releaseDate"))
    set_row.symbol_url = images.get("symbol")
    set_row.logo_url = images.get("logo")
    return set_row


async def upsert_card(db, raw: dict) -> Card:
    images = raw.get("images", {}) or {}
    tcgplayer = raw.get("tcgplayer", {}) or {}
    cardmarket = raw.get("cardmarket", {}) or {}

    card_row = await db.get(Card, raw["id"])
    if card_row is None:
        card_row = Card(id=raw["id"])
        db.add(card_row)

    card_row.name = raw.get("name", "")
    card_row.supertype = raw.get("supertype")
    card_row.subtypes = raw.get("subtypes")
    card_row.types = raw.get("types")
    card_row.hp = raw.get("hp")
    card_row.hp_int = parse_hp(raw.get("hp"))
    card_row.rarity = raw.get("rarity")
    card_row.number = raw.get("number")
    card_row.number_int = parse_card_number(raw.get("number"))
    card_row.artist = raw.get("artist")
    card_row.flavor_text = raw.get("flavorText")
    card_row.national_pokedex_numbers = raw.get("nationalPokedexNumbers")
    card_row.image_small = images.get("small")
    card_row.image_large = images.get("large")
    card_row.tcgplayer_url = tcgplayer.get("url")
    card_row.tcgplayer_prices = tcgplayer.get("prices")
    card_row.cardmarket_url = cardmarket.get("url")
    card_row.cardmarket_prices = cardmarket.get("prices")
    card_row.market_price_usd = _market_price_from_tcgplayer(tcgplayer.get("prices"))
    card_row.set_id = raw["set"]["id"]
    return card_row


async def seed(
    only_set: str | None = None,
    refresh: bool = False,
    sets_only: bool = False,
) -> None:
    await init_db()

    async with httpx.AsyncClient() as client:
        sets = await fetch_all_sets(client)
        if only_set:
            sets = [s for s in sets if s["id"] == only_set]
            if not sets:
                print(f"Set {only_set} not found.")
                return

        print(f"Found {len(sets)} sets.")

        async with SessionLocal() as db:
            for raw_set in sets:
                await upsert_set(db, raw_set)
            await db.commit()
            print(f"Upserted {len(sets)} sets.")

        if sets_only:
            return

        for idx, raw_set in enumerate(sets, start=1):
            set_id = raw_set["id"]

            if not refresh:
                async with SessionLocal() as db:
                    existing = await db.execute(
                        select(Card.id).where(Card.set_id == set_id).limit(1)
                    )
                    if existing.first() is not None:
                        print(f"[{idx}/{len(sets)}] {set_id} already has cards, skipping.")
                        continue

            print(f"[{idx}/{len(sets)}] Fetching cards for {set_id}…")
            try:
                cards = await fetch_cards_for_set(client, set_id)
            except httpx.HTTPError as e:
                print(f"  ! Failed to fetch {set_id}: {e}")
                continue

            async with SessionLocal() as db:
                for raw_card in cards:
                    await upsert_card(db, raw_card)
                await db.commit()
            print(f"  [OK] Upserted {len(cards)} cards for {set_id}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="only_set", help="Seed only this set id")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch existing data")
    parser.add_argument("--sets-only", action="store_true", help="Skip card details")
    args = parser.parse_args()

    asyncio.run(seed(only_set=args.only_set, refresh=args.refresh, sets_only=args.sets_only))


if __name__ == "__main__":
    main()
