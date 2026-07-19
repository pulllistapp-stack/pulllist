"""Relabel 7 sets that were imported as zh-cn but are actually zh-tw.

Background:
  TCGdex's zh-cn API returns 7 sets (SV7, SV7a, SV8, SV8a, SV9, SV9a,
  SV10) whose `name` field is Traditional Chinese not Simplified —
  they're Taiwan-market releases mislabeled at the source. Detected
  during the CN dedupe pass (2026-07-19); at the time we skipped
  them because we had no zh-tw locale surface. Now that Phase A ships
  the Taiwan region (asia.pokemon-card.com/tw importer), these seven
  belong there.

  E.g.
    zhcn-SV7  name='星晶奇跡'    (跡 is Traditional; SC would be 迹)
    zhcn-SV8a name='太晶慶典ex'  (慶 is Traditional; SC would be 庆)

Strategy:
  For each mislabeled set:
    1. Guard: refuse if a zhtw-{code} row already exists (would
       collide with a fresh Taiwan-scrape import), or if the set
       has products / collection references.
    2. Insert a new `zhtw-{code}` row carrying all the same
       metadata but with language='zh-tw' and series bilingualized
       to '朱＆紫 (Scarlet & Violet)' to match the KR/CN
       canonicalization pattern.
    3. Reassign every card: UPDATE cards SET set_id=<new>,
       language='zh-tw', id=REPLACE(id, 'zhcn-', 'zhtw-') WHERE
       set_id=<old>. The card IDs also flip prefix so the URL
       naming stays consistent with the rest of the zh-tw catalog.
    4. Delete the old zhcn-* row. Cards already reassigned, so
       the FK cascade doesn't touch them.

  Wrapped in a single transaction — partial failure rolls back.

Safety:
  - --dry-run prints the planned moves without touching the DB
  - --only <code> limits to one specific set (e.g. --only SV7)
  - Refuses to touch anything outside the whitelist of 7 codes
"""
from __future__ import annotations
import argparse
import asyncio
import io
import logging
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

MISLABELED = [
    "zhcn-SV7", "zhcn-SV7a",
    "zhcn-SV8", "zhcn-SV8a",
    "zhcn-SV9", "zhcn-SV9a",
    "zhcn-SV10",
]

# All 7 rows are Scarlet & Violet era — hardcode the bilingual series
# rather than trying to derive it from the (currently-null) series field
NEW_SERIES = "朱＆紫 (Scarlet & Violet)"


def _new_ids(old_set_id: str) -> str:
    """zhcn-SV7 → zhtw-SV7. Only the leading locale prefix flips."""
    assert old_set_id.startswith("zhcn-"), old_set_id
    return "zhtw-" + old_set_id[len("zhcn-"):]


async def guard_safe(db, old_id: str, new_id: str) -> tuple[bool, str]:
    # New ID must not exist
    n = (await db.execute(
        text("SELECT COUNT(*) FROM sets WHERE id = :i"), {"i": new_id}
    )).scalar_one()
    if n:
        return False, f"{new_id} already exists — collision"
    # No products (sealed rows) referencing old
    n = (await db.execute(
        text("SELECT COUNT(*) FROM products WHERE set_id = :i"), {"i": old_id}
    )).scalar_one()
    if n:
        return False, f"{old_id} has {n} products — need product-migration path"
    # No set_reports referencing old
    n = (await db.execute(
        text("SELECT COUNT(*) FROM set_reports WHERE set_id = :i"), {"i": old_id}
    )).scalar_one()
    if n:
        return False, f"{old_id} has {n} set_reports"
    return True, ""


async def relabel_one(db, old_id: str, dry_run: bool) -> tuple[int, str]:
    """Move one set. Returns (cards_moved, msg)."""
    new_id = _new_ids(old_id)
    ok, why = await guard_safe(db, old_id, new_id)
    if not ok:
        return 0, f"SKIP {old_id} → {why}"

    # Fetch old row
    r = await db.execute(text("""
        SELECT id, name, name_local, name_en, series, release_date, logo_url,
               (SELECT COUNT(*) FROM cards WHERE set_id=s.id) AS n_cards
        FROM sets s WHERE id = :i
    """), {"i": old_id})
    old = r.first()
    if not old:
        return 0, f"SKIP {old_id} → row not found"

    if dry_run:
        return old.n_cards, (
            f"PLAN {old_id} [{old.n_cards}c] → {new_id}  "
            f"name={old.name!r} series={old.series!r} → {NEW_SERIES!r}"
        )

    # 1. Insert new row
    await db.execute(text("""
        INSERT INTO sets (id, name, name_local, name_en, series, release_date,
                          logo_url, language, created_at, updated_at)
        VALUES (:i, :name, :name_local, :name_en, :series, :release,
                :logo, 'zh-tw', NOW(), NOW())
    """), {
        "i": new_id, "name": old.name, "name_local": old.name_local,
        "name_en": old.name_en, "series": NEW_SERIES,
        "release": old.release_date, "logo": old.logo_url,
    })

    # 2. Reassign cards. Card IDs also flip prefix so the URL stays
    #    consistent with the rest of the zh-tw catalog (zhtw-SV7-*).
    await db.execute(text("""
        UPDATE cards
           SET set_id  = :new_id,
               id      = REPLACE(id, :old_prefix, :new_prefix),
               language = 'zh-tw',
               updated_at = NOW()
         WHERE set_id = :old_id
    """), {
        "new_id": new_id, "old_id": old_id,
        "old_prefix": old_id + "-", "new_prefix": new_id + "-",
    })

    # 3. Drop the old row. Cards are gone (reassigned) so no cascade
    #    damage. Any residual FK (set_reports etc.) is caught by the
    #    guard above.
    await db.execute(text("DELETE FROM sets WHERE id = :i"), {"i": old_id})

    return old.n_cards, f"MOVED {old_id} → {new_id} ({old.n_cards} cards)"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None,
                    help="Only process the specific old set ID (e.g. zhcn-SV7)")
    args = ap.parse_args()

    targets = MISLABELED
    if args.only:
        if args.only not in MISLABELED:
            print(f"--only value must be one of: {MISLABELED}")
            return 2
        targets = [args.only]

    await init_db()
    async with SessionLocal() as db:
        total_cards = 0
        for old_id in targets:
            n, msg = await relabel_one(db, old_id, args.dry_run)
            print(f"  {msg}")
            total_cards += n
        if not args.dry_run:
            await db.commit()
            print(f"committed: {len(targets)} sets, {total_cards} cards relabeled")
        else:
            print(f"--dry-run: would relabel {len(targets)} sets, {total_cards} cards")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
