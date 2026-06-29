"""Restore the fpic-s2 (First Partner Illustration Series 2) set as a
standalone entry, undoing the earlier merge into mep.

Background:
    Before the TCGCSV bulk seed, fpic-s2 lived as its own set with 9
    Gen 2 / 5 / 8 starter promo cards (Chikorita / Cyndaquil /
    Totodile / Snivy / Tepig / Oshawott / Grookey / Scorbunny /
    Sobble). After mep got seeded from TCGCSV, those 9 cards showed
    up at mep-046 through mep-054 with proper product_ids + prices,
    so cleanup_fpic_s2_duplicates.py migrated the fpic-s2 rows into
    mep and deleted the fpic-s2 set.

    LO wants the fpic-s2 set restored as a standalone entry, like
    fpic-s1 still is. The 9 cards keep their priced TCGCSV rows but
    move out of mep into the fresh fpic-s2 set with new ids
    fpic-s2-046 .. fpic-s2-054.

What this script does:
    1. Upsert the fpic-s2 Set row, mirroring fpic-s1's metadata
       (series "Mega Evolution", local fps2.jpg logo asset that LO
       already dropped into /public/set-logos/).
    2. For each mep-NNN where NNN ∈ {046..054} and the card name
       matches one of the 9 Gen 2/5/8 starters:
          a. Insert a clone Card with id fpic-s2-NNN, set_id="fpic-s2",
             all other fields copied verbatim.
          b. Migrate CollectionItem / WishlistItem / CardReport refs
             from mep-NNN → fpic-s2-NNN (merge-on-collision pattern
             matches cleanup_duplicate_promos).
          c. Delete the now-orphaned mep-NNN row.

Idempotent — re-running with the set already in place + the cards
already moved is a no-op.

Run:
    python -m scripts.restore_fpic_s2_set --dry-run
    python -m scripts.restore_fpic_s2_set
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Card,
    CardReport,
    CollectionItem,
    Set,
    WishlistItem,
)

log = logging.getLogger("restore_fpic_s2_set")


# Pokémon names that belong to FPIC Series 2 (Gen 2 + Gen 5 + Gen 8
# starter trio). Used to verify we don't accidentally pull a non-
# starter mep card just because the number falls in 046..054.
S2_POKEMON = {
    "Chikorita", "Cyndaquil", "Totodile",
    "Snivy", "Tepig", "Oshawott",
    "Grookey", "Scorbunny", "Sobble",
}


async def main(dry_run: bool) -> None:
    stats = {
        "set_created": False,
        "cards_moved": 0,
        "cards_skipped_already_moved": 0,
        "collection_migrated": 0,
        "collection_merged": 0,
        "wishlist_migrated": 0,
        "wishlist_dropped": 0,
        "reports_rebound": 0,
        "old_cards_deleted": 0,
    }

    async with SessionLocal() as db:
        # ── 1. Upsert fpic-s2 Set ───────────────────────────────────
        existing_set = await db.get(Set, "fpic-s2")
        if existing_set is None:
            log.info("creating Set fpic-s2")
            if not dry_run:
                db.add(
                    Set(
                        id="fpic-s2",
                        name="First Partner Illustration Series 2",
                        series="Mega Evolution",
                        printed_total=9,
                        total=9,
                        language="en",
                        # NULL release_date so the /sets listing
                        # (release_date DESC nullslast) drops both
                        # fpic-* sets below the dated promo sets. We
                        # don't have a reliable date for these and
                        # leaving the column null is more honest than
                        # picking one — see also the matching update
                        # applied to fpic-s1.
                        release_date=None,
                        logo_url="/set-logos/fps2.jpg",
                        symbol_url=None,
                    )
                )
                await db.commit()
            stats["set_created"] = True
        else:
            log.info("Set fpic-s2 already exists; skipping create")

        # ── 2. Move the 9 starter cards mep → fpic-s2 ───────────────
        candidates = (
            await db.execute(
                select(Card)
                .where(
                    Card.set_id == "mep",
                    Card.number_int >= 46,
                    Card.number_int <= 54,
                )
                .order_by(Card.number_int)
            )
        ).scalars().all()

        for old_card in candidates:
            if old_card.name not in S2_POKEMON:
                log.warning(
                    "  mep-%s (%s) is in #46-54 range but not a"
                    " Gen 2/5/8 starter — skipping",
                    old_card.number, old_card.name,
                )
                continue

            new_id = f"fpic-s2-{old_card.number}"
            already = await db.get(Card, new_id)
            if already is not None:
                stats["cards_skipped_already_moved"] += 1
                log.info("  %s already exists; skipping", new_id)
                continue

            log.info(
                "  %s → %s  (%s, $%s)",
                old_card.id, new_id, old_card.name, old_card.market_price_usd,
            )
            if not dry_run:
                db.add(
                    Card(
                        id=new_id,
                        name=old_card.name,
                        supertype=old_card.supertype,
                        subtypes=old_card.subtypes,
                        types=old_card.types,
                        hp=old_card.hp,
                        hp_int=old_card.hp_int,
                        rarity=old_card.rarity,
                        number=old_card.number,
                        number_int=old_card.number_int,
                        artist=old_card.artist,
                        flavor_text=old_card.flavor_text,
                        national_pokedex_numbers=old_card.national_pokedex_numbers,
                        image_small=old_card.image_small,
                        image_large=old_card.image_large,
                        tcgplayer_url=old_card.tcgplayer_url,
                        tcgplayer_product_id=old_card.tcgplayer_product_id,
                        tcgplayer_prices=old_card.tcgplayer_prices,
                        market_price_usd=old_card.market_price_usd,
                        low_price_usd=old_card.low_price_usd,
                        high_price_usd=old_card.high_price_usd,
                        set_id="fpic-s2",
                        language=old_card.language,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
                await db.flush()

            # Migrate refs old → new (same merge-on-collision pattern
            # the dedup scripts use).
            coll_rows = (
                await db.execute(
                    select(CollectionItem).where(
                        CollectionItem.card_id == old_card.id
                    )
                )
            ).scalars().all()
            for ci in coll_rows:
                existing = (
                    await db.execute(
                        select(CollectionItem).where(
                            CollectionItem.user_id == ci.user_id,
                            CollectionItem.card_id == new_id,
                            CollectionItem.variant == ci.variant,
                            CollectionItem.condition == ci.condition,
                            CollectionItem.is_graded == ci.is_graded,
                            CollectionItem.grade == ci.grade,
                        )
                    )
                ).scalars().first()
                if existing:
                    if not dry_run:
                        existing.qty = (existing.qty or 0) + (ci.qty or 0)
                        await db.delete(ci)
                    stats["collection_merged"] += 1
                else:
                    if not dry_run:
                        ci.card_id = new_id
                    stats["collection_migrated"] += 1

            wish_rows = (
                await db.execute(
                    select(WishlistItem).where(
                        WishlistItem.card_id == old_card.id
                    )
                )
            ).scalars().all()
            for wi in wish_rows:
                existing_w = (
                    await db.execute(
                        select(WishlistItem).where(
                            WishlistItem.user_id == wi.user_id,
                            WishlistItem.card_id == new_id,
                            WishlistItem.variant == wi.variant,
                        )
                    )
                ).scalars().first()
                if existing_w:
                    if not dry_run:
                        await db.delete(wi)
                    stats["wishlist_dropped"] += 1
                else:
                    if not dry_run:
                        wi.card_id = new_id
                    stats["wishlist_migrated"] += 1

            rep_rows = (
                await db.execute(
                    select(CardReport).where(CardReport.card_id == old_card.id)
                )
            ).scalars().all()
            for r in rep_rows:
                if not dry_run:
                    r.card_id = new_id
                stats["reports_rebound"] += 1

            if not dry_run:
                await db.delete(old_card)
            stats["old_cards_deleted"] += 1
            stats["cards_moved"] += 1

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
