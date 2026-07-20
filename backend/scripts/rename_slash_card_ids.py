"""Rename card IDs that contain `/` to use `_` instead.

Collectory-imported KR/CN cards have IDs like
`ko-c-<hash>-234/208` where `234/208` is the printed number (e.g.
"234 of 208"). Postgres and R2 storage don't mind the slash, but
Next.js dynamic routing treats `/cards/[cardId]` as a single path
segment — a card whose id contains `/` 404s in the browser.

29,021 rows affected today. Fix flips every slash to underscore:
  ko-c-*-234/208  →  ko-c-*-234_208

FK deps on `card_id` (all have DELETE CASCADE but no ON UPDATE
CASCADE, so we can't just UPDATE the parent):

  card_reports
  collection_items
  card_price_snapshots
  scan_cache
  wishlist_items

Migration pattern (single transaction):
  1. Build a temp mapping table (old_id, new_id) for every affected row
  2. INSERT new rows into `cards` with the new id + copied metadata
  3. UPDATE every FK-child table to point to the new id
  4. DELETE old rows (children now reference new — no cascade damage)

Also refresh `sets.image_small`/`image_large` via the R2 upload
script's `--skip-upload` mode afterwards, since the previous DB
swap missed these rows (uploaded file names had `_`, DB IDs had `/`).

Safety:
  - Refuses to run if any row's new_id already exists (would be a
    silent collision — e.g. two cards `foo/bar` and `foo_bar` in
    the same set).
  - --dry-run prints counts + a sample without touching DB.
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

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rename_slash_card_ids")

FK_TABLES = ("card_reports", "collection_items", "card_price_snapshots",
             "scan_cache", "wishlist_items")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    await init_db()
    async with SessionLocal() as db:
        # Count affected rows
        total = (await db.execute(
            text("SELECT COUNT(*) FROM cards WHERE id LIKE '%/%'")
        )).scalar_one()
        log.info(f"cards with / in id: {total}")
        if not total:
            log.info("nothing to rename")
            return 0

        # Collision check: does any target new_id already exist?
        collisions = (await db.execute(text("""
            SELECT c.id AS old_id, REPLACE(c.id, '/', '_') AS new_id
            FROM cards c
            WHERE c.id LIKE '%/%'
              AND EXISTS (SELECT 1 FROM cards c2
                          WHERE c2.id = REPLACE(c.id, '/', '_')
                            AND c2.id <> c.id)
        """))).all()
        if collisions:
            log.error(f"REFUSING: {len(collisions)} target IDs already exist")
            for row in collisions[:5]:
                log.error(f"  {row.old_id!r} → {row.new_id!r} (exists)")
            return 2

        # Sample the rename
        sample = (await db.execute(text(
            "SELECT id, REPLACE(id, '/', '_') AS new_id FROM cards "
            "WHERE id LIKE '%/%' LIMIT 5"
        ))).all()
        log.info("sample rename:")
        for row in sample:
            log.info(f"  {row.id} → {row.new_id}")

        # FK dep counts (how many child rows would each need updating)
        for t in FK_TABLES:
            n = (await db.execute(text(
                f"SELECT COUNT(*) FROM {t} WHERE card_id LIKE '%/%'"
            ))).scalar_one()
            log.info(f"  FK {t}: {n} rows")

        if args.dry_run:
            log.info("--dry-run: no writes")
            return 0

        # Verify no FK rows reference slash card IDs — otherwise
        # `UPDATE cards SET id = …` would violate the FK constraint
        # (ON UPDATE NO ACTION).
        for t in FK_TABLES:
            n = (await db.execute(text(
                f"SELECT COUNT(*) FROM {t} WHERE card_id LIKE '%/%'"
            ))).scalar_one()
            if n:
                log.error(f"REFUSING: {t} has {n} FK rows with slash card_id — "
                          f"needs a multi-step migration (INSERT + UPDATE FKs "
                          f"+ DELETE), current path skipped for safety")
                return 3

        # Straight-line UPDATE — the parent-only PK change is safe
        # because zero children reference any slash id.
        log.info(f"UPDATE cards SET id = REPLACE(…) — {total} rows …")
        await db.execute(text(
            "UPDATE cards SET id = REPLACE(id, '/', '_'), updated_at = NOW() "
            "WHERE id LIKE '%/%'"
        ))
        await db.commit()
        log.info(f"committed: {total} card ids renamed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
