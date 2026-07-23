"""Wire up subset → parent Set relationships.

Pokemon TCG splits certain themed subsets into standalone Set rows
(Shiny Vault, Trainer Gallery, Galarian Gallery, Classic Collection).
Users see them as duplicate tiles on /sets. We reuse the pre-existing
`Set.parent_set_id` column (originally introduced for translation
relationships, currently unused) to record the subset-of relationship
so the sets list endpoint can hide subsets and roll their cards into
the parent tile.

Runs on the same 8 known EN pairs. Idempotent — re-running only fixes
rows whose parent_set_id doesn't match the target.

Usage:
    python -m scripts.link_subset_parents             # apply
    python -m scripts.link_subset_parents --dry-run   # print plan only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models.set import Set


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("link_subsets")


# child_id → parent_id
SUBSET_PAIRS: dict[str, str] = {
    # Sun & Moon
    "sma": "sm115",             # Hidden Fates Shiny Vault → Hidden Fates
    # Sword & Shield
    "swsh45sv": "swsh45",       # Shining Fates Shiny Vault → Shining Fates
    "swsh9tg": "swsh9",         # Brilliant Stars TG → Brilliant Stars
    "swsh10tg": "swsh10",       # Astral Radiance TG → Astral Radiance
    "swsh11tg": "swsh11",       # Lost Origin TG → Lost Origin
    "swsh12tg": "swsh12",       # Silver Tempest TG → Silver Tempest
    "swsh12pt5gg": "swsh12pt5", # Crown Zenith Galarian Gallery → Crown Zenith
    "cel25c": "cel25",          # Celebrations Classic Collection → Celebrations
}


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        child_ids = list(SUBSET_PAIRS.keys())
        parent_ids = list(set(SUBSET_PAIRS.values()))

        # Fetch all involved rows in one shot for validation + logging.
        existing = {
            r.id: r
            for r in (
                await db.execute(select(Set).where(Set.id.in_(child_ids + parent_ids)))
            ).scalars().all()
        }

        applied = 0
        skipped = 0
        missing = 0

        for child_id, parent_id in SUBSET_PAIRS.items():
            child = existing.get(child_id)
            parent = existing.get(parent_id)

            if child is None:
                log.warning(f"[miss] child {child_id!r} not in DB — skip")
                missing += 1
                continue
            if parent is None:
                log.warning(
                    f"[miss] parent {parent_id!r} not in DB — cannot link "
                    f"{child_id!r} → nothing"
                )
                missing += 1
                continue

            if child.parent_set_id == parent_id:
                log.info(
                    f"[skip] {child_id!r} ({child.name}) already → {parent_id!r}"
                )
                skipped += 1
                continue

            log.info(
                f"[link] {child_id!r} ({child.name}) → {parent_id!r} "
                f"({parent.name})"
            )
            if not dry_run:
                child.parent_set_id = parent_id
                applied += 1

        if not dry_run:
            await db.commit()

        log.info(f"\n=== summary ===")
        log.info(f"  linked:  {applied}")
        log.info(f"  skipped: {skipped}")
        log.info(f"  missing: {missing}")
        log.info(f"  dry_run: {dry_run}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
