"""Manual seed: Pokémon TCG First Partner Illustration Collection.

pokemontcg.io and Limitless don't index these promo cards (even three
months after Series 1's release), so we INSERT them directly from
pokemon.com's product gallery asset URLs. Same shape as our
pokemontcg.io seed flow — set + card rows — just with a hand-curated
source.

Set-id convention `fpic-s{N}` won't collide with pokemontcg.io's
lowercase single-token style (`svp`, `sv8`, etc.), so if they ever
index these, the future canonical rows live alongside ours and we
migrate manually.

Card numbers match the printed "MEP EN ###" tag on each card — Series 1
runs 037–045, Series 2 runs 046–054, ordered Grass → Fire → Water
within each region (Kanto / Sinnoh / Alola for Series 1; Johto /
Unova / Galar for Series 2).

Card images come straight from www.pokemon.com's CDN — the host serves
these PNGs cross-origin without hot-link protection. weserv's free
proxy blocks pokemon.com by policy so we can't launder them through
there. www.pokemon.com is whitelisted in next.config.mjs.

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
    "https://www.pokemon.com/static-assets/content-assets/"
    "cms2/img/cards/full/MEP/MEP_EN_{mep:02d}.png"
)


def _image(mep_num: int) -> str:
    return _POKEMON_CDN.format(mep=mep_num)


SETS = [
    {
        # Display name dropped "Collection —" because the verbatim set name
        # is fed into the eBay Browse query (see services/ebay_client.py
        # `build_card_query`); an em-dash + the word "Collection" added two
        # tokens that eBay seller titles rarely match, killing recall. The
        # canonical product name is still "First Partner Illustration
        # Collection—Series 1" — we just shorten in our catalog so the
        # eBay match path doesn't take a hit.
        "id": "fpic-s1",
        "name": "First Partner Illustration Series 1",
        "series": "Mega Evolution",
        "printed_total": 9,
        "total": 9,
        "release_date": date(2026, 3, 20),
        "logo_url": "/set-logos/fps1.jpg",
    },
    {
        "id": "fpic-s2",
        "name": "First Partner Illustration Series 2",
        "series": "Mega Evolution",
        "printed_total": 9,
        "total": 9,
        "release_date": date(2026, 6, 19),
        "logo_url": "/set-logos/fps2.jpg",
    },
]


# (set_id, mep_num, name, types, hp, artist)
# mep_num drives BOTH the printed card number ("037") and the
# pokemon.com CDN filename (MEP_EN_037.png). HPs for cards verified
# against LO's card photos; unknown HPs (Series 2 mid-stages we
# haven't seen yet) stay None — site hides the HP chip when null.
# Artist filled where the "Illus. Saboteri" signature was visible.
CARDS = [
    # Series 1 — Kanto / Sinnoh / Alola starters (037–045)
    ("fpic-s1", 37, "Bulbasaur",  ["Grass"], 80, "Saboteri"),
    ("fpic-s1", 38, "Charmander", ["Fire"],  80, "Saboteri"),
    ("fpic-s1", 39, "Squirtle",   ["Water"], 80, "Saboteri"),
    ("fpic-s1", 40, "Turtwig",    ["Grass"], 90, "Saboteri"),
    ("fpic-s1", 41, "Chimchar",   ["Fire"],  60, "Saboteri"),
    ("fpic-s1", 42, "Piplup",     ["Water"], 70, "Saboteri"),
    ("fpic-s1", 43, "Rowlet",     ["Grass"], 70, "Saboteri"),
    ("fpic-s1", 44, "Litten",     ["Fire"],  70, "Saboteri"),
    ("fpic-s1", 45, "Popplio",    ["Water"], 70, "Saboteri"),
    # Series 2 — Johto / Unova / Galar starters (046–054)
    ("fpic-s2", 46, "Chikorita",  ["Grass"], None, None),
    ("fpic-s2", 47, "Cyndaquil",  ["Fire"],  None, None),
    ("fpic-s2", 48, "Totodile",   ["Water"], 80,   "Saboteri"),
    ("fpic-s2", 49, "Snivy",      ["Grass"], 60,   "Saboteri"),
    ("fpic-s2", 50, "Tepig",      ["Fire"],  80,   "Saboteri"),
    ("fpic-s2", 51, "Oshawott",   ["Water"], None, None),
    ("fpic-s2", 52, "Grookey",    ["Grass"], None, None),
    ("fpic-s2", 53, "Scorbunny",  ["Fire"],  70,   "Saboteri"),
    ("fpic-s2", 54, "Sobble",     ["Water"], None, None),
]


async def seed() -> None:
    await init_db()

    # Defensive cleanup: an earlier version of this script numbered
    # cards 1..9 per series. The current schema uses the printed MEP
    # number (037..054) so card ids shift; without an explicit delete
    # the old rows linger as orphans. No-op if the placeholder ids
    # were never written (fresh installs skip this branch entirely).
    placeholder_ids = [f"fpic-s1-{i}" for i in range(1, 10)] + [
        f"fpic-s2-{i}" for i in range(1, 10)
    ]
    async with SessionLocal() as db:
        wiped = 0
        for old_id in placeholder_ids:
            row = await db.get(Card, old_id)
            if row is not None:
                await db.delete(row)
                wiped += 1
        if wiped:
            await db.commit()
            print(f"Cleaned {wiped} stale rows from prior numbering scheme.")

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
            if s.get("logo_url"):
                row.logo_url = s["logo_url"]
        await db.commit()
        print(f"Upserted {len(SETS)} sets.")

    async with SessionLocal() as db:
        for set_id, mep_num, name, types, hp, artist in CARDS:
            # Card id keyed on MEP number so re-running this script is a
            # pure upsert and never duplicates rows even if we re-shuffle
            # the metadata.
            card_id = f"{set_id}-{mep_num:03d}"
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
            row.number = f"{mep_num:03d}"
            row.number_int = mep_num
            row.artist = artist
            row.image_small = _image(mep_num)
            row.image_large = _image(mep_num)
            row.set_id = set_id
        await db.commit()
        print(f"Upserted {len(CARDS)} cards.")


if __name__ == "__main__":
    asyncio.run(seed())
