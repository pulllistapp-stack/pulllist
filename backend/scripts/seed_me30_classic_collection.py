"""Seed 11 Classic Collection reprints into me30 (30th Celebration).

LO's call (2026-07-07): don't spin up a separate me30cc set — fold the
classic reprints straight into me30 since they'll ship as part of the
30th anniversary product. Print numbers on the actual reprints aren't
public yet, so we use placeholder codes CC01..CC11 (number_int 1001..
1011 so they sort at the tail of the set) and null out image_small
until the reprint art is available.

Metadata (name, hp, supertype, subtypes, types, national_pokedex_numbers)
is copied from the original card row so the reprint carries the same
Pokémon identity; only the set_id, id, number, rarity, artist, and
image are new.

Idempotent — re-running is a no-op after the first successful pass.
"""

import asyncio

from sqlalchemy import select
from app.database import SessionLocal
from app.models.card import Card


REPRINTS = [
    ("base1-4",     "CC01", 1001),  # Charizard, Rare Holo
    ("base1-58",    "CC02", 1002),  # Pikachu, Common
    ("dp4-106",     "CC03", 1003),  # Palkia LV.X
    ("dp6-43",      "CC04", 1004),  # Uxie
    ("ecard2-149",  "CC05", 1005),  # Lugia, Rare Secret
    ("hgss4-99",    "CC06", 1006),  # Darkrai & Cresselia LEGEND (top)
    ("hgss4-100",   "CC07", 1007),  # Darkrai & Cresselia LEGEND (bottom)
    ("sm9-33",      "CC08", 1008),  # Pikachu & Zekrom-GX
    ("swsh1-138",   "CC09", 1009),  # Zacian V
    ("swsh4-50",    "CC10", 1010),  # Raikou (Amazing Rare)
    ("swsh9-123",   "CC11", 1011),  # Arceus VSTAR
]


async def main() -> None:
    async with SessionLocal() as db:
        skipped = 0
        added = 0
        for orig_id, cc_num, cc_int in REPRINTS:
            new_id = f"me30-cc-{cc_int - 1000:02d}"

            # Idempotency: skip if already inserted.
            existing = await db.get(Card, new_id)
            if existing is not None:
                print(f"[skip] {new_id} already exists")
                skipped += 1
                continue

            orig = await db.get(Card, orig_id)
            if orig is None:
                print(f"[warn] original {orig_id} not found; skipping")
                continue

            reprint = Card(
                id=new_id,
                name=orig.name,
                supertype=orig.supertype,
                subtypes=orig.subtypes,
                types=orig.types,
                hp=orig.hp,
                hp_int=orig.hp_int,
                rarity="Classic Collection",
                number=cc_num,
                number_int=cc_int,
                artist=orig.artist,
                national_pokedex_numbers=orig.national_pokedex_numbers,
                # Reprint art is a new print with anniversary treatment —
                # not the original scan. Null until TCGCSV / pokemon.com
                # publishes the actual reprint image.
                image_small=None,
                image_large=None,
                set_id="me30",
                language="en",
            )
            db.add(reprint)
            added += 1
            print(f"[add ] {new_id} <- {orig_id}  {orig.name}  ({cc_num})")

        await db.commit()
        print(f"\n[done] added={added} skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
