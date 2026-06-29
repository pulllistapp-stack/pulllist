"""One-shot cleanup for two unrelated promo-set housekeeping tasks
LO spotted in the UI after the promo seed:

  1. `pptp` (Player Placement Trainer Promos) — TCGplayer ships no
     card images for any of these 4 cards (No. 1 Trainer 2012 etc.),
     they're invisible in our card grid. Drop the whole set.

  2. `mep` (ME: Mega Evolution Promo) — no logo/symbol because
     pokemontcg.io never indexed it. Borrow the `me1` ("Mega
     Evolution") set's logo + symbol so the set-detail header has
     the right ME era branding.

  3. `swsd` (SWSH: Sword & Shield Promo Cards) — same gap; reuse
     `swshp` (SWSH Black Star Promos) art so it visually slots in
     with the rest of the SWSH-era promos.

Idempotent. Re-running after success deletes nothing extra and the
logo backfills become no-ops once the columns are non-null.

Run:
    python -m scripts.cleanup_pptp_and_set_logos --dry-run
    python -m scripts.cleanup_pptp_and_set_logos
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

from sqlalchemy import delete, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Card,
    CardReport,
    CollectionItem,
    Set,
    WishlistItem,
)

log = logging.getLogger("cleanup_pptp_and_set_logos")


LOGO_DONORS = {
    "mep": "me1",     # ME: Mega Evolution Promo  ← Mega Evolution
    "swsd": "swshp",  # SWSH: S&S Promo Cards     ← SWSH Black Star Promos
}


async def main(dry_run: bool) -> None:
    stats = {
        "pptp_cards_deleted": 0,
        "pptp_set_deleted": False,
        "pptp_coll_refs": 0,
        "pptp_wish_refs": 0,
        "pptp_report_refs": 0,
        "logos_backfilled": 0,
    }

    async with SessionLocal() as db:
        # ── 1. Drop pptp ────────────────────────────────────────────
        pptp_cards = (
            await db.execute(
                select(Card.id).where(Card.set_id == "pptp")
            )
        ).scalars().all()
        if pptp_cards:
            log.info("pptp has %d cards — purging", len(pptp_cards))
            # Just in case anyone added them to collection/wishlist
            # since seed, count + delete the refs first.
            coll_n = (
                await db.execute(
                    select(CollectionItem).where(
                        CollectionItem.card_id.in_(pptp_cards)
                    )
                )
            ).scalars().all()
            wish_n = (
                await db.execute(
                    select(WishlistItem).where(
                        WishlistItem.card_id.in_(pptp_cards)
                    )
                )
            ).scalars().all()
            rep_n = (
                await db.execute(
                    select(CardReport).where(
                        CardReport.card_id.in_(pptp_cards)
                    )
                )
            ).scalars().all()
            stats["pptp_coll_refs"] = len(coll_n)
            stats["pptp_wish_refs"] = len(wish_n)
            stats["pptp_report_refs"] = len(rep_n)
            if not dry_run:
                for r in (*coll_n, *wish_n, *rep_n):
                    await db.delete(r)
                res = await db.execute(
                    delete(Card).where(Card.set_id == "pptp")
                )
                stats["pptp_cards_deleted"] = res.rowcount or 0
            else:
                stats["pptp_cards_deleted"] = len(pptp_cards)

            pptp_set = await db.get(Set, "pptp")
            if pptp_set is not None:
                if not dry_run:
                    await db.delete(pptp_set)
                stats["pptp_set_deleted"] = True
        else:
            log.info("pptp already empty / dropped, skipping")

        # ── 2. Backfill logos for mep + swsd ────────────────────────
        for target_sid, donor_sid in LOGO_DONORS.items():
            target = await db.get(Set, target_sid)
            donor = await db.get(Set, donor_sid)
            if target is None:
                log.warning("target set %s missing, skipping", target_sid)
                continue
            if donor is None:
                log.warning(
                    "donor set %s missing for %s, skipping",
                    donor_sid,
                    target_sid,
                )
                continue
            touched = False
            if not target.logo_url and donor.logo_url:
                log.info(
                    "  %s.logo_url ← %s (%s)",
                    target_sid, donor_sid, donor.logo_url,
                )
                if not dry_run:
                    target.logo_url = donor.logo_url
                touched = True
            if not target.symbol_url and donor.symbol_url:
                log.info(
                    "  %s.symbol_url ← %s (%s)",
                    target_sid, donor_sid, donor.symbol_url,
                )
                if not dry_run:
                    target.symbol_url = donor.symbol_url
                touched = True
            if touched:
                stats["logos_backfilled"] += 1

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
