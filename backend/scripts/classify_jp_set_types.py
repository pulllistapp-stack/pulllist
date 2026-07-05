"""Add sets.set_type column and classify all JP sets.

Categories:
    MAIN           — main booster expansion (SV1, PMCG1, Dark Rush, etc.)
    DECK           — starter set / deck / trainer box / build box / etc.
    STUB           — set exists in catalog but no cards seeded (mostly TCGdex
                     rows we never populated: ADV1-5, L1a/b, PCG10, etc.)
    PROMO_LEGACY   — existing JP promo groups shown on the promo grid
                     (JPP-P, JPP-SI, JPP-VM, JPP-BWP, JPP-DPP, etc.)
    PROMO_NEW      — Bulbapedia-derived year buckets grouped by 5-year window
                     (JPP-U1996 covering 1996-2005, JPP-U2006, U2007, ...)

Also deletes 8 Triplet Beat duplicate stubs (CS1.5, CS1a-b, CS2.5, CS2a-b,
CS3.5, sv1a) where the actual set is SV1a with cards.

Usage:
    cd backend
    python -m scripts.classify_jp_set_types --dry-run
    python -m scripts.classify_jp_set_types           # applies

Idempotent: safe to re-run. Only touches language='ja' rows.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db
from scripts.utils.set_classifier import classify_set

log = logging.getLogger("classify_jp_set_types")

# 8 Triplet Beat duplicate stubs — actual set is SV1a with cards.
_DELETE_DUPES = {
    "CS1.5", "CS1a", "CS1b", "CS2.5", "CS2a", "CS2b", "CS3.5", "sv1a",
}


async def run(dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # 1) Add column (idempotent). Schema migration always runs so the
        # subsequent SELECT can reference the column in --dry-run.
        log.info("adding sets.set_type column (if not exists)")
        await db.execute(text(
            "ALTER TABLE sets ADD COLUMN IF NOT EXISTS set_type VARCHAR(20)"
        ))
        await db.commit()

        # 2) Fetch all JP sets
        rows = (await db.execute(text("""
            SELECT id, name, name_en, set_type,
                   (SELECT COUNT(*) FROM cards WHERE cards.set_id = sets.id) as cnt
            FROM sets WHERE language='ja'
        """))).all()
        log.info(f"fetched {len(rows)} JP sets")

        stats = {"MAIN": 0, "DECK": 0, "STUB": 0,
                 "PROMO_LEGACY": 0, "PROMO_NEW": 0,
                 "unchanged": 0, "deleted": 0}

        deletions = []
        updates = []

        for row in rows:
            if row.id in _DELETE_DUPES:
                if row.cnt == 0:
                    deletions.append(row.id)
                else:
                    log.warning(f"skip delete {row.id}: {row.cnt} cards attached")
                continue

            new_type = classify_set(row.id, row.name, row.name_en, row.cnt)
            stats[new_type] += 1
            if row.set_type == new_type:
                stats["unchanged"] += 1
                continue
            updates.append((row.id, new_type))

        log.info("=== distribution ===")
        for k in ("MAIN", "DECK", "STUB", "PROMO_LEGACY", "PROMO_NEW"):
            log.info(f"  {k:15s} {stats[k]:4d}")
        log.info(f"  {'to update':15s} {len(updates):4d}")
        log.info(f"  {'to delete':15s} {len(deletions):4d}  ({deletions})")

        # 3) Apply updates
        if not dry and updates:
            for sid, t in updates:
                await db.execute(
                    text("UPDATE sets SET set_type=:t, updated_at=NOW() WHERE id=:i"),
                    {"t": t, "i": sid},
                )
            await db.commit()
            log.info(f"applied {len(updates)} set_type updates")

        # 4) Apply deletions
        if not dry and deletions:
            for sid in deletions:
                await db.execute(text("DELETE FROM sets WHERE id=:i"), {"i": sid})
            await db.commit()
            log.info(f"deleted {len(deletions)} Triplet Beat duplicate stubs")

    log.info("done")
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
