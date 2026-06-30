"""Populate sets.name_en for JP sets — "JP Name (English Name)" labels.

Strategy (audit-verified 2026-06-30):

1. Auto-match: any JP set whose id matches an EN set id (case-
   insensitive) inherits the EN set's name. Covers modern mainline
   (SM6→Forbidden Light, XY2→Flashfire, SV3→Obsidian Flames etc.)
   where both languages use the same id.

2. Manual vintage 1:1: PMCG1 (拡張パック = Base Set 1996) and E1
   (基本拡張パック = Expedition Base Set) are true 1:1 in
   numbering, name_en is safe.

3. EVERYTHING ELSE → name_en stays / becomes NULL. We deliberately
   skip:
   - PMCG2-6 (Jungle/Fossil/Team Rocket/Gym Heroes/Gym Challenge):
     same expansion name but JP/EN numbering split (PMCG6 audit
     showed 7/10 card mismatch). Showing the EN label here would
     imply 1:1 which is false.
   - E2-E5 (Aquapolis+Skyridge cover 4 JP sets in 2)
   - PCG1-9 (EX-series numbering shifts vs JP PCG ordering)
   - JP-only sets (VS, web, JPP-*, ADV-*, CS-*, SVK, SVLS, SVLN,
     SM mini-sets like SMP/SMA/SMC, etc.) — no EN equivalent at all.

Re-runnable + idempotent.

Usage:
    python -m scripts.backfill_jp_set_name_en --dry-run
    python -m scripts.backfill_jp_set_name_en
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jp_set_name_en")

# Vintage / non-mainline-id mappings. Two categories:
#   (a) clean 1:1 (PMCG1, E1) — both expansion identity and card
#       numbering line up with the EN equivalent.
#   (b) expansion-name match only (PMCG2-6) — the JP set was released
#       as the JP version of the named EN expansion, BUT card
#       numbering doesn't line up 1:1 (esp. Gym era: JP 96+98 vs EN
#       132+132). We still surface the EN expansion name so users
#       recognize the set ("基本拡張パック (Base Set)"); card-level
#       cross-link is a separate concern (see ROADMAP §10.6.3).
VINTAGE_1_TO_1: dict[str, str] = {
    "PMCG1": "Base Set",
    "PMCG2": "Jungle",
    "PMCG3": "Fossil",
    "PMCG4": "Team Rocket",
    "PMCG5": "Gym Heroes",
    "PMCG6": "Gym Challenge",
    "E1": "Expedition Base Set",
}


async def run(dry: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        # First: clear stale name_en so we don't keep old wrong mappings.
        # Only reset entries that didn't come from this run's whitelist.
        if not dry:
            await db.execute(text("""
                UPDATE sets SET name_en = NULL
                WHERE language='ja' AND name_en IS NOT NULL
            """))

        # 1) Auto-match by id (case-insensitive)
        auto_rows = (await db.execute(text("""
            SELECT j.id, e.name
            FROM sets j
            JOIN sets e ON LOWER(e.id) = LOWER(j.id) AND e.language='en'
            WHERE j.language='ja'
            ORDER BY j.id
        """))).all()
        log.info(f"Auto-matched JP↔EN sets by id: {len(auto_rows)}")
        for jp_id, en_name in auto_rows:
            log.info(f"  {jp_id} → {en_name}")
            if not dry:
                await db.execute(text("""
                    UPDATE sets SET name_en=:en WHERE id=:i AND language='ja'
                """), {"en": en_name, "i": jp_id})

        # 2) Manual vintage 1:1
        log.info(f"\nManual vintage 1:1 ({len(VINTAGE_1_TO_1)}):")
        for jp_id, en_name in VINTAGE_1_TO_1.items():
            log.info(f"  {jp_id} → {en_name}")
            if not dry:
                await db.execute(text("""
                    UPDATE sets SET name_en=:en WHERE id=:i AND language='ja'
                """), {"en": en_name, "i": jp_id})

        if not dry:
            await db.commit()

        # Final tally
        n = (await db.execute(text(
            "SELECT COUNT(*) FROM sets WHERE language='ja' AND name_en IS NOT NULL"
        ))).scalar()
        t = (await db.execute(text("SELECT COUNT(*) FROM sets WHERE language='ja'"))).scalar()
        log.info(f"\nFinal: {n}/{t} JP sets have name_en ({(n/t)*100:.1f}%)")
        if dry:
            log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
