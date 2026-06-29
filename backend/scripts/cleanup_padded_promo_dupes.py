"""Pass 2 cleanup: zero-padding dupes within the same promo set.

The product-id dedup pass caught any pair that shared a
tcgplayer_product_id. What it couldn't catch: pairs where the legacy
pokemontcg.io row never had a product_id at all (older imports), but
the TCGCSV row I just seeded duplicates it with zero-padded numbering.

Example (post-Pass-1 state):
    svp-3     name="Quaxly"      number="3"    number_int=3   pid=None  $2.73
    svp-003   name="Quaxly"      number="003"  number_int=3   pid=477183 $None

Same Pokémon, same number, only the id-string padding differs. Safe
merge: keep the legacy row (has the price + historical user refs),
back-fill product_id + image from the new row, delete the new row.

Rule (deliberately tight to avoid false positives):
    set_id matches AND
    number_int matches (not None) AND
    cleaned name matches EXACTLY (case-insensitive, trimmed)

Cards with a parenthetical variant tag ("(Cosmos Holo)", "(Pokemon
Center Exclusive)", "(Prerelease)", "(Staff)") DO NOT match an
unlabeled sibling — those are genuinely distinct SKUs. They remain
as separate rows.

Winner selection mirrors cleanup_duplicate_promos.py:
    1. has market_price_usd
    2. most CollectionItem refs
    3. most WishlistItem refs
    4. shortest id

Run:
    python -m scripts.cleanup_padded_promo_dupes --dry-run
    python -m scripts.cleanup_padded_promo_dupes
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections import defaultdict
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

log = logging.getLogger("cleanup_padded_promo_dupes")


SEEDED: set[str] = {
    "mep", "svp", "swsd", "smp", "xyp", "bwp", "hgssp", "dpp", "bop",
    "wotcp", "pptp", "ppp", "pwcp", "aap", "np", "kwbp", "ccp", "bkp",
    "md25anniv", "md24", "md23", "md22", "md19", "md18", "md17",
    "md16", "md15", "md14", "md12", "md11",
}


def _norm_name(n: str | None) -> str:
    return (n or "").strip().lower()


async def _coll_count(db, cid: str) -> int:
    return int(
        (
            await db.execute(
                select(func.count(CollectionItem.id)).where(
                    CollectionItem.card_id == cid
                )
            )
        ).scalar() or 0
    )


async def _wish_count(db, cid: str) -> int:
    return int(
        (
            await db.execute(
                select(func.count(WishlistItem.id)).where(
                    WishlistItem.card_id == cid
                )
            )
        ).scalar() or 0
    )


async def _pick_winner(db, cards: list[Card]) -> Card:
    scored: list[tuple[Card, tuple]] = []
    for c in cards:
        has_price = 1 if c.market_price_usd is not None else 0
        cc = await _coll_count(db, c.id)
        wc = await _wish_count(db, c.id)
        scored.append((c, (has_price, cc, wc, -len(c.id))))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[0][0]


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
        "clusters_merged": 0,
        "losers_deleted": 0,
        "backfilled_fields": 0,
        "collection_migrated": 0,
        "collection_merged": 0,
        "wishlist_migrated": 0,
        "wishlist_dropped": 0,
        "reports_rebound": 0,
        "empty_sets_deleted": 0,
        "skipped_variant_mismatch": 0,
    }

    async with SessionLocal() as db:
        for sid in sorted(SEEDED):
            rows = (
                await db.execute(
                    select(Card).where(Card.set_id == sid)
                )
            ).scalars().all()
            if not rows:
                continue

            # Group only when number_int is set (variant-only ids
            # like 'SWSH092' typically have number_int=None and end
            # up grouped together incorrectly — skip those).
            buckets: dict[tuple[int, str], list[Card]] = defaultdict(list)
            for c in rows:
                if c.number_int is None:
                    continue
                buckets[(c.number_int, _norm_name(c.name))].append(c)

            for (num, name_lower), cs in buckets.items():
                if len(cs) < 2:
                    continue
                stats["clusters_merged"] += 1
                winner = await _pick_winner(db, cs)
                losers = [c for c in cs if c.id != winner.id]
                log.info(
                    "[%s] '%s' #%d  winner=%s ($%s)  losers=%s",
                    sid,
                    name_lower,
                    num,
                    winner.id,
                    winner.market_price_usd,
                    [l.id for l in losers],
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
                await db.flush()

        if not dry_run:
            await db.commit()

        # Empty-set sweep (same as Pass 1)
        for sid in SEEDED:
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
