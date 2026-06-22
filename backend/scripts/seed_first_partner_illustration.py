"""Manual seed: Pokémon TCG First Partner Illustration Collection.

pokemontcg.io and Limitless don't index these promo cards (even three
months after Series 1's release), so we INSERT them directly from
pokemon.com's product gallery asset URLs. Same shape as our
pokemontcg.io seed flow — set + card rows — just with a hand-curated
source.

Set-id convention `fpic-s{N}` won't collide with pokemontcg.io's
lowercase single-token style (`svp`, `sv8`, etc.), so if they ever
index these, the future canonical rows live alongside ours and we
migrate manually. Card images come straight from pokemon.com's CDN —
the host serves these PNGs cross-origin without hot-link protection,
and weserv's free proxy blocks pokemon.com by policy so we can't
launder them through there. assets.pokemon.com is whitelisted in the
frontend's next.config.mjs remotePatterns.

Run:
    python -m scripts.seed_first_partner_illustration
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db
from app.models import Card, Set

_POKEMON_CDN = (
    "https://assets.pokemon.com/static-assets/content-assets/"
    "cms2/img/cards/full/MEP/MEP_EN_{mep:02d}.png"
)


def _image(mep_num: int) -> str:
    return _POKEMON_CDN.format(mep=mep_num)


SETS = [
    {
        "id": "fpic-s1",
        "name": "First Partner Illustration Collection — Series 1",
        "series": "Scarlet & Violet",
        "printed_total": 9,
        "total": 9,
        "release_date": date(2026, 3, 20),
    },
    {
        "id": "fpic-s2",
        "name": "First Partner Illustration Collection — Series 2",
        "series": "Scarlet & Violet",
        "printed_total": 9,
        "total": 9,
        "release_date": date(2026, 6, 19),
    },
]


# (set_id, card_number, MEP image index, name, types, hp)
# Card numbers go 1/9 .. 9/9 per series. MEP index is the pokemon.com
# CDN filename — sequential 37..45 (Series 1), 46..54 (Series 2).
# HP values for Series 1 read off LO's screenshot of the 9 cards; for
# Series 2 we don't have a card image yet so HP stays NULL — the page
# still renders the name + image + type, only the HP chip is hidden.
CARDS = [
    # Series 1 — Kanto / Sinnoh / Alola starters
    ("fpic-s1", 1, 37, "Bulbasaur",  ["Grass"], 80),
    ("fpic-s1", 2, 38, "Charmander", ["Fire"],  80),
    ("fpic-s1", 3, 39, "Squirtle",   ["Water"], 80),
    ("fpic-s1", 4, 40, "Turtwig",    ["Grass"], 90),
    ("fpic-s1", 5, 41, "Chimchar",   ["Fire"],  60),
    ("fpic-s1", 6, 42, "Piplup",     ["Water"], 70),
    ("fpic-s1", 7, 43, "Rowlet",     ["Grass"], 70),
    ("fpic-s1", 8, 44, "Litten",     ["Fire"],  70),
    ("fpic-s1", 9, 45, "Popplio",    ["Water"], 70),
    # Series 2 — Johto / Unova / Galar starters
    ("fpic-s2", 1, 46, "Cyndaquil",  ["Fire"],  None),
    ("fpic-s2", 2, 47, "Totodile",   ["Water"], None),
    ("fpic-s2", 3, 48, "Chikorita",  ["Grass"], None),
    ("fpic-s2", 4, 49, "Snivy",      ["Grass"], None),
    ("fpic-s2", 5, 50, "Tepig",      ["Fire"],  None),
    ("fpic-s2", 6, 51, "Oshawott",   ["Water"], None),
    ("fpic-s2", 7, 52, "Grookey",    ["Grass"], None),
    ("fpic-s2", 8, 53, "Scorbunny",  ["Fire"],  None),
    ("fpic-s2", 9, 54, "Sobble",     ["Water"], None),
]


async def seed() -> None:
    await init_db()

    async with SessionLocal() as db:
        for s in SETS:
            row = await db.get(Set, s["id"])
            if row is None:
                row = Set(id=s["id"])
                db.add(row)
            row.name = s["name"]
            row.series = s["series"]
            row.printed_total = s["printed_total"]
            row.total = s["total"]
            row.release_date = s["release_date"]
        await db.commit()
        print(f"Upserted {len(SETS)} sets.")

    async with SessionLocal() as db:
        for set_id, number, mep_num, name, types, hp in CARDS:
            card_id = f"{set_id}-{number}"
            row = await db.get(Card, card_id)
            if row is None:
                row = Card(id=card_id)
                db.add(row)
            row.name = name
            row.supertype = "Pokémon"
            row.subtypes = ["Basic"]
            row.types = types
            row.hp = str(hp) if hp is not None else None
            row.hp_int = hp
            row.rarity = "Illustration Rare"
            row.number = f"{number}/9"
            row.number_int = number
            row.image_small = _image(mep_num)
            row.image_large = _image(mep_num)
            row.set_id = set_id
        await db.commit()
        print(f"Upserted {len(CARDS)} cards.")


if __name__ == "__main__":
    asyncio.run(seed())
