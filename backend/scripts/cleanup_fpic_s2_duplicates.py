"""Cleanup fpic-s2 (First Partner Illustration Series 2) duplicates.

fpic-s2 was manually seeded earlier when MEP wasn't in our catalog.
Now that seed_all_promos has pulled MEP from TCGCSV, mep-046 through
mep-054 cover the same 9 Pokemon (Chikorita/Cyndaquil/Totodile/Snivy/
Tepig/Oshawott/Grookey/Scorbunny/Sobble) with proper TCGplayer
product ids + live pricing.

This script:
  1. For each fpic-s2-NNN card, looks up the corresponding mep-NNN
     by card number.
  2. Migrates CollectionItem rows pointing at fpic-s2 → mep, handling
     the unique-constraint case where the user already had a matching
     mep row (sums qty into the survivor, deletes the duplicate).
  3. Same for WishlistItem rows.
  4. Same for CardReport rows (just rebinds card_id; no uniqueness
     constraint to worry about).
  5. Deletes fpic-s2 cards.
  6. Deletes the fpic-s2 Set row.

Idempotent — if there's nothing to migrate the script just reports
zero changes and exits.

fpic-s1 is NOT touched — those 9 cards (Bulbasaur/Charmander/Squirtle/
Turtwig/Chimchar/Piplup/Rowlet/Litten/Popplio) are Gen 1+4+7 First
Partner cards and have no MEP equivalents.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Card,
    CardReport,
    CollectionItem,
    Set,
    WishlistItem,
)


log = logging.getLogger("cleanup_fpic_s2_duplicates")


async def main(dry_run: bool) -> None:
    stats = {
        "collection_migrated": 0,
        "collection_merged": 0,
        "wishlist_migrated": 0,
        "wishlist_dropped_as_dup": 0,
        "reports_rebound": 0,
        "cards_deleted": 0,
        "set_deleted": False,
    }

    async with SessionLocal() as db:
        fpic_cards = (
            await db.execute(
                select(Card).where(Card.set_id == "fpic-s2")
            )
        ).scalars().all()
        log.info("fpic-s2 cards in DB: %d", len(fpic_cards))

        for fc in fpic_cards:
            # Match by number — mep-NNN of same number is the survivor
            mep_id = f"mep-{fc.number}"
            mep_card = await db.get(Card, mep_id)
            if mep_card is None:
                log.warning(
                    "  fpic-s2 %s #%s → no mep-%s exists, skipping",
                    fc.id, fc.number, fc.number,
                )
                continue
            log.info("  fpic-s2 %s #%s → mep-%s", fc.id, fc.number, fc.number)

            # ── CollectionItem migration ────────────────────────────
            coll_rows = (
                await db.execute(
                    select(CollectionItem).where(
                        CollectionItem.card_id == fc.id
                    )
                )
            ).scalars().all()
            for ci in coll_rows:
                # Look for an existing row keyed by mep-* with the
                # same variant/condition/grade for this user.
                existing = (
                    await db.execute(
                        select(CollectionItem).where(
                            CollectionItem.user_id == ci.user_id,
                            CollectionItem.card_id == mep_id,
                            CollectionItem.variant == ci.variant,
                            CollectionItem.condition == ci.condition,
                            CollectionItem.is_graded == ci.is_graded,
                            CollectionItem.grade == ci.grade,
                        )
                    )
                ).scalars().first()

                if existing:
                    # Merge into the survivor — sum qty, then drop fpic row
                    if not dry_run:
                        existing.qty = (existing.qty or 0) + (ci.qty or 0)
                        await db.delete(ci)
                    stats["collection_merged"] += 1
                    log.info(
                        "    coll: merged qty %d into existing %s",
                        ci.qty, existing.id,
                    )
                else:
                    if not dry_run:
                        ci.card_id = mep_id
                    stats["collection_migrated"] += 1
                    log.info("    coll: rebound %s → %s", ci.id, mep_id)

            # ── WishlistItem migration ──────────────────────────────
            wish_rows = (
                await db.execute(
                    select(WishlistItem).where(
                        WishlistItem.card_id == fc.id
                    )
                )
            ).scalars().all()
            for wi in wish_rows:
                existing = (
                    await db.execute(
                        select(WishlistItem).where(
                            WishlistItem.user_id == wi.user_id,
                            WishlistItem.card_id == mep_id,
                            WishlistItem.variant == wi.variant,
                        )
                    )
                ).scalars().first()
                if existing:
                    if not dry_run:
                        await db.delete(wi)
                    stats["wishlist_dropped_as_dup"] += 1
                    log.info(
                        "    wish: dropped %s (mep-%s wish already exists)",
                        wi.id, fc.number,
                    )
                else:
                    if not dry_run:
                        wi.card_id = mep_id
                    stats["wishlist_migrated"] += 1
                    log.info("    wish: rebound %s → %s", wi.id, mep_id)

            # ── CardReport migration ────────────────────────────────
            rep_rows = (
                await db.execute(
                    select(CardReport).where(CardReport.card_id == fc.id)
                )
            ).scalars().all()
            for r in rep_rows:
                if not dry_run:
                    r.card_id = mep_id
                stats["reports_rebound"] += 1

        if not dry_run:
            await db.commit()

        # ── Now delete fpic-s2 cards + set ──────────────────────────
        if not dry_run:
            del_cards = await db.execute(
                delete(Card).where(Card.set_id == "fpic-s2")
            )
            stats["cards_deleted"] = del_cards.rowcount or 0

            fpic_set = await db.get(Set, "fpic-s2")
            if fpic_set is not None:
                await db.delete(fpic_set)
                stats["set_deleted"] = True

            await db.commit()
        else:
            stats["cards_deleted"] = len(fpic_cards)

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %s: %s", k, v)
    log.info("  dry_run: %s", dry_run)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.dry_run))
