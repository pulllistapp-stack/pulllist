"""Fix national_pokedex_numbers entries stored as floats (e.g. 384.1)
that break the API's Pydantic list[int] validator.

A handful of vintage JP cards (PCG2/6/7/9, ~4 rows as of 2026-06-30)
were imported with float values in this column — likely a delta-species
marker in the source. The dex number is the integer part; the decimal
was artisan annotation that should never have landed in the int list.

Floors each entry and rewrites the column. Idempotent and safe to
re-run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("fix_dex_number_floats")


async def run(dry: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        rows = (await db.execute(text(r"""
            SELECT id, national_pokedex_numbers
            FROM cards
            WHERE national_pokedex_numbers::text ~ '\.'
        """))).all()
        log.info(f"Found {len(rows)} cards with float dex_numbers")
        for cid, nums in rows:
            floored = [int(n) for n in nums]
            log.info(f"  {cid}: {nums} -> {floored}")
            if not dry:
                # asyncpg can't bind a Python list to a JSON column
                # directly — encode to JSON text and cast in SQL.
                await db.execute(text("""
                    UPDATE cards SET national_pokedex_numbers = CAST(:n AS JSONB)
                    WHERE id = :i
                """), {"n": json.dumps(floored), "i": cid})
        if not dry and rows:
            await db.commit()
            log.info(f"Wrote {len(rows)} rows.")
        elif dry:
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
