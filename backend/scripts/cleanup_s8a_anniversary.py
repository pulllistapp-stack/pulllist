"""Clean up the 25th Anniversary set family after the import pass.

Two artifacts to clear:

1) S8a card table has 4 duplicate Pikachu V-UNION panel rows
   (`S8a-025/028 (Top Left)`, "(Top Right)", "(Bottom Left)",
   "(Bottom Right)") because the earlier import_jp_group_cards regex
   didn't strip the parenthesised suffix from TCGCSV numbers. The
   canonical S8a-25/26/27/28 rows already exist (updated in-place
   during the same import), so the four suffixed rows are pure
   duplicates safe to delete.

2) Bulbapedia lists S8a's total as 30 (28 numbered + 2 SR), but the
   set row currently carries total=28 from an older seed. Fix it so
   the completion counter on /sets/S8a stops undercounting after the
   Mew #030 UR backfill.

Idempotent — DELETE only targets rows matching the exact suffixed
ids, and the S8a total UPDATE is a no-op after the first successful
run.

Usage:
    python -m scripts.cleanup_s8a_anniversary --dry-run
    python -m scripts.cleanup_s8a_anniversary
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402


log = logging.getLogger("cleanup_s8a_anniversary")


_BOGUS_S8A_ROWS = [
    "S8a-025/028 (Top Left)",
    "S8a-026/028 (Top Right)",
    "S8a-027/028 (Bottom Left)",
    "S8a-028/028 (Bottom Right)",
]


async def run(dry_run: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        # 1. Inspect the bogus rows first so we log what we're touching.
        rows = (await db.execute(
            text(
                "SELECT id, name, number FROM cards "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": _BOGUS_S8A_ROWS},
        )).all()
        log.info(f"bogus S8a rows found: {len(rows)}")
        for r in rows:
            log.info(f"  {r.id}  number={r.number!r}  name={r.name!r}")

        # 2. Also check current S8a total.
        s = (await db.execute(
            text("SELECT id, total, printed_total FROM sets WHERE id = 'S8a'")
        )).first()
        if s:
            log.info(
                f"S8a set row: total={s.total} printed_total={s.printed_total}"
            )

        if dry_run:
            log.info("MODE: DRY-RUN — no writes")
            return

        # 3. Delete bogus rows.
        if rows:
            r = await db.execute(
                text("DELETE FROM cards WHERE id = ANY(:ids)"),
                {"ids": _BOGUS_S8A_ROWS},
            )
            log.info(f"deleted rows: {r.rowcount}")

        # 4. Bump S8a total to 30 (Bulbapedia-official: 28 base + 2 SR).
        r2 = await db.execute(
            text(
                "UPDATE sets SET total = 30 "
                "WHERE id = 'S8a' AND (total IS NULL OR total < 30)"
            )
        )
        log.info(f"S8a total updated rows: {r2.rowcount}")

        await db.commit()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
