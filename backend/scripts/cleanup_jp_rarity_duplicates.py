"""Reset high-tier rarity (SIR/HR/UR/etc.) on JP DECK reprints that
inherited it wrongly from backfill_jp_rarity.py.

Root cause:
    backfill_jp_rarity.py fetched each JP card's list of EN print
    equivalents from Limitless, then used a "secret rare threshold"
    (JP number > 85% of set total → secret rare) to pick between
    candidates. DECK sets (Starter Deck 100 Battle Collection MC,
    MEGA Starter Sets MBG/MBD, ex Starter Sets SVA*, etc.) hold
    REPRINTS of MAIN-set cards. Their card numbers are in the
    reprint's DECK set (e.g. MC-694 for アイリスの闘志 in a
    766-card MC set), which is >85% of the DECK set's total, so
    the heuristic mis-classified them as secret rares and grabbed
    the SAR/UR rarity of the same-name card living in some other
    MAIN set.

Impact (verified 2026-07-06):
    409 JP cards labeled Special Illustration Rare, of which 197
    (48%) are duplicates by name — mostly DECK reprints of
    supporter cards (ボスの指令 37x, ネモ 20x, ナンジャモ 15x)
    that only have 1–3 legitimate SAR prints in main sets.

This script is intentionally conservative:
    - Only resets rarity for cards in DECK sets (set_type='DECK').
    - Only downgrades tiers that are clearly wrong for a DECK
      reprint: Special Illustration Rare, Hyper Rare, Ultra Rare,
      Rare Secret, Illustration Rare, Rainbow Rare, Triple Rare,
      Special Rare, Shiny Ultra Rare, Rare ACE, Amazing Rare,
      Radiant Rare, Mega Hyper Rare.
    - Sets rarity to NULL so scrape_bulbapedia_jp_rarity.py (or a
      future JP-native source) can fill in the correct tier.
    - Leaves Common / Uncommon / Rare / Rare Holo / Double Rare
      alone — those are plausible reprint tiers.

Idempotent. Prints affected cards before writing.

Usage:
    python -m scripts.cleanup_jp_rarity_duplicates --dry-run
    python -m scripts.cleanup_jp_rarity_duplicates
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("cleanup_jp_rarity_duplicates")

# Rarity tiers that a DECK-set reprint should almost never legitimately
# carry. Reset these to NULL and let a proper JP-native source refill.
_UNPLAUSIBLE_DECK_RARITIES: tuple[str, ...] = (
    "Special Illustration Rare",
    "Hyper Rare",
    "Ultra Rare",
    "Rare Ultra",
    "Rare Secret",
    "Illustration Rare",
    "Rainbow Rare",
    "Triple Rare",
    "Special Rare",
    "Shiny Ultra Rare",
    "Rare ACE",
    "Amazing Rare",
    "Radiant Rare",
    "Mega Hyper Rare",
)


async def run(dry: bool, verbose: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT c.id, c.name, c.rarity, c.set_id, s.name AS set_name
            FROM cards c
            JOIN sets s ON s.id = c.set_id
            WHERE c.language = 'ja'
              AND s.set_type = 'DECK'
              AND c.rarity = ANY(:tiers)
            ORDER BY c.rarity, c.set_id, c.number_int NULLS LAST, c.id
        """), {"tiers": list(_UNPLAUSIBLE_DECK_RARITIES)})).all()

    from collections import Counter
    by_rarity = Counter(r.rarity for r in rows)
    log.info(f"Targets: {len(rows)} JP DECK cards carrying an implausible rarity")
    for tier, n in by_rarity.most_common():
        log.info(f"  {n:4d}  {tier}")

    if verbose:
        for row in rows:
            n = (row.name or "?").encode("ascii", "replace").decode("ascii")[:30]
            log.info(f"  reset  {row.id:20s}  {n:30s}  {row.rarity}")

    if rows and not dry:
        async with SessionLocal() as db:
            await db.execute(
                text("""
                    UPDATE cards SET rarity = NULL, updated_at = NOW()
                    WHERE id = ANY(:ids)
                """),
                {"ids": [r.id for r in rows]},
            )
            await db.commit()
        log.info(f"reset {len(rows)} rows → rarity=NULL")

    if dry:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true",
                   help="Print every card being reset")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run, args.verbose))


if __name__ == "__main__":
    main()
