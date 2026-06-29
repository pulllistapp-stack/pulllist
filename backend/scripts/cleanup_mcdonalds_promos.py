"""Pass 3 cleanup: merge `md*` (TCGCSV) into `mcd*` (legacy
pokemontcg.io) McDonald's promo sets.

Background:
    pokemontcg.io imported McDonald's sets as `mcd11`..`mcd22` with
    series="Other" (which is why they show up under the "OTHER"
    section in the UI rather than under a McDonald's heading).

    seed_all_promos pulled the same physical cards from TCGCSV into
    `md11`..`md25anniv` with series="McDonald's" and full TCGplayer
    product_ids. None of them shared a product_id with the legacy
    `mcd*` rows (legacy rows had pid=None), so Pass-1 product-id
    dedup couldn't merge them.

    Inspection confirms md14 and mcd14 ship identical 12-card lists
    (Weedle/Chespin/Fennekin/...) in identical numbering, just
    different id schemes. Same for every other year.

What this script does:
    1. For each (new, legacy) pair below:
        - For each card in `new`, find the `legacy` sibling by
          (number_int, normalized name).
        - Back-fill product_id / image / tcgplayer_url onto the
          legacy row (so the price sync starts populating it).
        - Migrate CollectionItem / WishlistItem / CardReport refs
          from new → legacy.
        - Delete the new card row.
    2. Re-tag every mcd* set's series → "McDonald's" so the UI
       groups them under the same heading as the surviving
       single-source set.
    3. Delete any md* set that's now empty.

Mapping (md → mcd):
    md11       → mcd11
    md12       → mcd12
    md14       → mcd14
    md15       → mcd15
    md16       → mcd16
    md17       → mcd17
    md18       → mcd18
    md19       → mcd19   (md19 may already be empty)
    md22       → mcd22
    md25anniv  → mcd21   (McDonald's 25th Anniversary was 2021)

Run:
    python -m scripts.cleanup_mcdonalds_promos --dry-run
    python -m scripts.cleanup_mcdonalds_promos
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Card,
    CardReport,
    CollectionItem,
    Set,
    WishlistItem,
)

log = logging.getLogger("cleanup_mcdonalds_promos")


SET_MAP: dict[str, str] = {
    "md11": "mcd11",
    "md12": "mcd12",
    "md14": "mcd14",
    "md15": "mcd15",
    "md16": "mcd16",
    "md17": "mcd17",
    "md18": "mcd18",
    "md19": "mcd19",
    "md22": "mcd22",
    "md25anniv": "mcd21",
}


def _norm(n: str | None) -> str:
    return (n or "").strip().lower()


def _backfill(winner: Card, loser: Card, dry_run: bool) -> int:
    touched = 0
    fields = [
        "image_small",
        "image_large",
        "tcgplayer_url",
        "tcgplayer_product_id",
        "rarity",
        "hp",
        "hp_int",
        "types",
        "supertype",
        "number_int",
    ]
    for f in fields:
        win_val = getattr(winner, f, None)
        lose_val = getattr(loser, f, None)
        if win_val in (None, "", []) and lose_val not in (None, "", []):
            if not dry_run:
                setattr(winner, f, lose_val)
            touched += 1
    return touched


async def _migrate_refs(
    db, winner_id: str, loser_id: str, dry_run: bool, stats: dict
) -> None:
    coll_rows = (
        await db.execute(
            select(CollectionItem).where(CollectionItem.card_id == loser_id)
        )
    ).scalars().all()
    for ci in coll_rows:
        existing = (
            await db.execute(
                select(CollectionItem).where(
                    CollectionItem.user_id == ci.user_id,
                    CollectionItem.card_id == winner_id,
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
                ci.card_id = winner_id
            stats["collection_migrated"] += 1

    wish_rows = (
        await db.execute(
            select(WishlistItem).where(WishlistItem.card_id == loser_id)
        )
    ).scalars().all()
    for wi in wish_rows:
        existing_w = (
            await db.execute(
                select(WishlistItem).where(
                    WishlistItem.user_id == wi.user_id,
                    WishlistItem.card_id == winner_id,
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
                wi.card_id = winner_id
            stats["wishlist_migrated"] += 1

    rep_rows = (
        await db.execute(
            select(CardReport).where(CardReport.card_id == loser_id)
        )
    ).scalars().all()
    for r in rep_rows:
        if not dry_run:
            r.card_id = winner_id
        stats["reports_rebound"] += 1


async def main(dry_run: bool) -> None:
    stats = {
        "pairs_processed": 0,
        "cards_merged": 0,
        "cards_kept_in_new": 0,
        "backfilled_fields": 0,
        "collection_migrated": 0,
        "collection_merged": 0,
        "wishlist_migrated": 0,
        "wishlist_dropped": 0,
        "reports_rebound": 0,
        "series_retagged": 0,
        "empty_sets_deleted": 0,
    }

    async with SessionLocal() as db:
        # ── Step 1: per-pair merge ──────────────────────────────────
        for new_sid, legacy_sid in SET_MAP.items():
            stats["pairs_processed"] += 1
            new_cards = (
                await db.execute(
                    select(Card).where(Card.set_id == new_sid)
                )
            ).scalars().all()
            if not new_cards:
                log.info("%s already empty, skipping", new_sid)
                continue
            legacy_cards = (
                await db.execute(
                    select(Card).where(Card.set_id == legacy_sid)
                )
            ).scalars().all()
            legacy_by_key = {
                (c.number_int, _norm(c.name)): c
                for c in legacy_cards
                if c.number_int is not None
            }

            for nc in new_cards:
                key = (nc.number_int, _norm(nc.name))
                legacy = legacy_by_key.get(key)
                if legacy is None:
                    log.warning(
                        "  %s no legacy sibling for #%s %s — leaving in place",
                        new_sid, nc.number, nc.name,
                    )
                    stats["cards_kept_in_new"] += 1
                    continue
                stats["backfilled_fields"] += _backfill(legacy, nc, dry_run)
                await _migrate_refs(
                    db, legacy.id, nc.id, dry_run, stats
                )
                if not dry_run:
                    await db.delete(nc)
                stats["cards_merged"] += 1
                log.info(
                    "  %s/#%s %s → %s",
                    new_sid, nc.number, nc.name, legacy.id,
                )

            if not dry_run:
                await db.flush()

        # ── Step 2: re-tag mcd* series ──────────────────────────────
        legacy_sets = (
            await db.execute(
                select(Set).where(Set.id.in_(list(SET_MAP.values())))
            )
        ).scalars().all()
        for s in legacy_sets:
            if s.series != "McDonald's":
                log.info(
                    "  retag %s series '%s' → 'McDonald\\'s'",
                    s.id, s.series,
                )
                if not dry_run:
                    s.series = "McDonald's"
                stats["series_retagged"] += 1

        if not dry_run:
            await db.commit()

        # ── Step 3: drop empty md* sets ─────────────────────────────
        for new_sid in SET_MAP:
            cnt = (
                await db.execute(
                    select(func.count(Card.id)).where(Card.set_id == new_sid)
                )
            ).scalar() or 0
            if cnt == 0:
                set_row = await db.get(Set, new_sid)
                if set_row is not None:
                    log.info("  drop empty seeded set: %s", new_sid)
                    if not dry_run:
                        await db.delete(set_row)
                    stats["empty_sets_deleted"] += 1
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
