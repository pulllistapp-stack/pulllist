"""Cleanup ALL promo duplicates created by the seed_all_promos run.

Background:
    seed_all_promos.py pulled 30 TCGCSV promo groups into our DB.
    Several of those groups overlap with sets pokemontcg.io had
    already imported under different naming conventions:

      - svp:   old `svp-44`  vs new `svp-044`  (same set id, different
               number padding) — internal dupe.
      - bwp/np:   same shape (numbered-and-padded vs unpadded).
      - wotcp ↔ basep, hgssp ↔ hsp, swsd ↔ swshp, bop ↔ bp
      - md11~md25anniv ↔ mcd11~mcd22 / mcd21
      - mep ↔ fpic-s1 (3 First Partner cards: Chimchar, Piplup, Rowlet)

    All of those overlaps end up with the SAME tcgplayer_product_id on
    the new + old rows (TCGplayer's product is the canonical key).

    Genuine new variants (Pokemon Center Exclusive, Cosmos Holo,
    Prerelease, Staff) have their OWN product_id that never matches
    anything else — those rows survive untouched.

Strategy:
    Pass 1 — Product-id dedup
        For every cluster of cards sharing the same
        tcgplayer_product_id (count >= 2):
            * pick a canonical winner:
                  1. row with a non-null market_price_usd
                  2. row with the most CollectionItem refs
                  3. row with the shortest id (older naming)
            * back-fill any null fields on the winner from the loser
              (image_large, tcgplayer_url, rarity, etc.) — so we never
              regress data when keeping the legacy row.
            * migrate CollectionItem / WishlistItem / CardReport rows
              from losers → winner.
            * delete loser Card rows.

    Pass 2 — Empty-set sweep
        Any Set row I created in seed_all_promos that's now
        completely empty after Pass 1 gets dropped.

Run:
    python -m scripts.cleanup_duplicate_promos --dry-run     # report
    python -m scripts.cleanup_duplicate_promos               # commit

Re-runnable. If a cluster has already been merged, it's a no-op.
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

from sqlalchemy import delete, func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Card,
    CardReport,
    CollectionItem,
    Set,
    WishlistItem,
)


log = logging.getLogger("cleanup_duplicate_promos")


# Sets created by seed_all_promos. Pass-2 sweep only deletes Set rows
# whose id is in this list AND whose card count drops to 0 after the
# product-id merge.
SEEDED_SET_IDS: set[str] = {
    "mep", "svp", "swsd", "smp", "xyp", "bwp", "hgssp", "dpp", "bop",
    "wotcp", "pptp", "ppp", "pwcp", "aap", "np", "kwbp", "ccp", "bkp",
    "md25anniv", "md24", "md23", "md22", "md19", "md18", "md17",
    "md16", "md15", "md14", "md12", "md11",
}


async def _pick_winner(db, cards: list[Card]) -> Card:
    """Pick the canonical row for a dup cluster.

    Priority:
        1. has non-null market_price_usd
        2. has the most CollectionItem rows
        3. has the most WishlistItem rows
        4. shortest id (legacy naming was shorter)
    """
    async def coll_count(card_id: str) -> int:
        v = (
            await db.execute(
                select(func.count(CollectionItem.id)).where(
                    CollectionItem.card_id == card_id
                )
            )
        ).scalar()
        return int(v or 0)

    async def wish_count(card_id: str) -> int:
        v = (
            await db.execute(
                select(func.count(WishlistItem.id)).where(
                    WishlistItem.card_id == card_id
                )
            )
        ).scalar()
        return int(v or 0)

    scored: list[tuple[Card, tuple]] = []
    for c in cards:
        has_price = 1 if c.market_price_usd is not None else 0
        cc = await coll_count(c.id)
        wc = await wish_count(c.id)
        scored.append(
            (c, (has_price, cc, wc, -len(c.id)))  # higher tuple wins
        )
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[0][0]


def _backfill(winner: Card, loser: Card, dry_run: bool) -> int:
    """Copy non-null fields from loser onto winner where winner is null.

    Returns number of fields touched. Useful when the loser was the
    only side carrying e.g. a TCGplayer URL or large image — we keep
    the legacy row but absorb its richer metadata.
    """
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
    db,
    winner_id: str,
    loser_id: str,
    dry_run: bool,
    stats: dict,
) -> None:
    """Move CollectionItem / WishlistItem / CardReport from loser
    onto winner. Handle unique-constraint collisions by merging qty
    (collection) or dropping the loser row (wishlist)."""
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
        "clusters": 0,
        "losers_deleted": 0,
        "backfilled_fields": 0,
        "collection_migrated": 0,
        "collection_merged": 0,
        "wishlist_migrated": 0,
        "wishlist_dropped": 0,
        "reports_rebound": 0,
        "empty_sets_deleted": 0,
    }

    async with SessionLocal() as db:
        # ── Pass 1: product_id clusters ─────────────────────────────
        clusters = (
            await db.execute(
                select(Card.tcgplayer_product_id, func.count(Card.id))
                .where(Card.tcgplayer_product_id.isnot(None))
                .group_by(Card.tcgplayer_product_id)
                .having(func.count(Card.id) > 1)
            )
        ).all()
        log.info("found %d product_id clusters with >=2 cards", len(clusters))

        for pid, _cnt in clusters:
            cards = (
                await db.execute(
                    select(Card)
                    .where(Card.tcgplayer_product_id == pid)
                )
            ).scalars().all()
            if len(cards) < 2:
                continue

            stats["clusters"] += 1
            winner = await _pick_winner(db, cards)
            losers = [c for c in cards if c.id != winner.id]
            log.info(
                "pid=%s  winner=%s ($%s set=%s)  losers=%s",
                pid,
                winner.id,
                winner.market_price_usd,
                winner.set_id,
                [c.id for c in losers],
            )

            for loser in losers:
                stats["backfilled_fields"] += _backfill(
                    winner, loser, dry_run
                )
                await _migrate_refs(
                    db, winner.id, loser.id, dry_run, stats
                )
                if not dry_run:
                    await db.delete(loser)
                stats["losers_deleted"] += 1

            if not dry_run:
                # Flush between clusters so backfills + ref migrations
                # are visible before the next select() runs.
                await db.flush()

        if not dry_run:
            await db.commit()

        # ── Pass 2: empty seeded sets ───────────────────────────────
        for sid in SEEDED_SET_IDS:
            cnt = (
                await db.execute(
                    select(func.count(Card.id)).where(Card.set_id == sid)
                )
            ).scalar() or 0
            if cnt == 0:
                set_row = await db.get(Set, sid)
                if set_row is not None:
                    log.info("dropping empty seeded set: %s", sid)
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
