"""Sub-classify JP DECK products into 4 buckets for the browser.

Buckets (matches option 2 from LO's review):
    STARTER  — Starter Set / Starter Pack / VMAX/ex Starter / MEGA Starter
    DECK     — Character-focused competitive decks, half decks, evolution packs
    BOX      — Premium Trainer Box, Deck Build Box, Trainer Box
    SPECIAL  — Battle Gift Set, VMAX/VSTAR Special Set, Jumbo-Pack Set,
               Championship Deck, Family Pokémon, Collection Sheet, etc.

Also hides S8a "25th Anniversary Collection" — LO called it out as a
one-off anniversary product they'd rather not see in the deck grid.
The row survives, just moves to set_type='STUB' so the frontend hides
it alongside the empty vintage stubs.

Adds sets.set_subtype VARCHAR(16) if missing. Idempotent.

Usage:
    python -m scripts.classify_deck_subtypes --dry-run
    python -m scripts.classify_deck_subtypes
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("classify_deck_subtypes")


# Ordered — first regex match wins. Order matters: BOX patterns first
# so "Deck Build Box" doesn't fall through to plain "deck".
_SUBTYPE_RULES: list[tuple[str, list[str]]] = [
    ("BOX", [
        r"deck build box", r"master deck build",
        r"trainer box", r"premium trainer",
        r"battle box", r"deck battle box",
    ]),
    ("SPECIAL", [
        r"special set", r"special deck set", r"special card set",
        r"battle gift set", r"gift set",
        r"jumbo-?pack set",
        r"world championships?",
        r"championship deck",
        r"family pok",
        r"collection sheet",
        r"battle partners deck build",  # already caught by BOX but harmless
        r"dragon selection",
        r"zamazenta box",
        r"evolution pack",
    ]),
    ("STARTER", [
        r"starter set", r"starter pack", r"starting set",
        r"terastal starter",
        r"mega starter",
        r"ex starter",
        r"vmax starter set", r"vstar starter set",
        r"tag team gx starter", r"gx starter deck",
        r"v starter deck",
        r"tapu bulu-gx", r"solgaleo-gx", r"lunala-gx",
    ]),
    # Fallthrough: DECK — anything else DECK
    ("DECK", [r"deck", r"battle master", r"high-class", r"perfect battle"]),
]

# Set IDs to hide from the browser entirely (kept in DB but set_type
# flips to STUB). LO's call on which anniversary-flavoured products
# should stay off the deck grid.
_HIDE_SET_IDS: set[str] = {
    "S8a",  # 25th Anniversary Collection
}


def classify_deck_subtype(name: str, name_en: str | None = None) -> str:
    """Return the sub-bucket label for a DECK set. Defaults to DECK."""
    n = ((name_en or "") + " " + (name or "")).lower()
    for label, patterns in _SUBTYPE_RULES:
        for p in patterns:
            if re.search(p, n):
                return label
    return "DECK"


async def run(dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # 1) Column
        log.info("adding sets.set_subtype column (if not exists)")
        await db.execute(text(
            "ALTER TABLE sets ADD COLUMN IF NOT EXISTS set_subtype VARCHAR(16)"
        ))
        await db.commit()

        # 2) Hide the anniversary one-offs
        if not dry:
            for sid in _HIDE_SET_IDS:
                r = await db.execute(
                    text("UPDATE sets SET set_type='STUB', updated_at=NOW() "
                         "WHERE id=:i AND set_type <> 'STUB'"),
                    {"i": sid},
                )
                if r.rowcount:
                    log.info(f"  hidden: {sid} (set_type STUB)")
            await db.commit()
        else:
            log.info(f"  would hide: {_HIDE_SET_IDS}")

        # 3) Fetch remaining DECK rows and classify
        rows = (await db.execute(text("""
            SELECT id, name, name_en, set_subtype FROM sets
            WHERE language='ja' AND set_type='DECK'
        """))).all()
        log.info(f"DECK rows to sub-classify: {len(rows)}")

        from collections import Counter
        dist = Counter()
        updates = []
        for row in rows:
            sub = classify_deck_subtype(row.name, row.name_en)
            dist[sub] += 1
            if row.set_subtype != sub:
                updates.append((row.id, sub))

        for sub, n in dist.most_common():
            log.info(f"  {sub:10s} {n}")
        log.info(f"  to update: {len(updates)}")

        if updates and not dry:
            for sid, sub in updates:
                await db.execute(
                    text("UPDATE sets SET set_subtype=:s, updated_at=NOW() WHERE id=:i"),
                    {"s": sub, "i": sid},
                )
            await db.commit()
            log.info(f"applied {len(updates)} set_subtype updates")

    if dry:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
