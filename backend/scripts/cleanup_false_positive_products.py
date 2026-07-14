"""Purge single-card SKUs mis-ingested into the sealed products table.

Root cause: the pre-fix `_looks_sealed` matched sealed hints as bare
substrings, so "tin" fired on `Giratina` / `Victini` / `Dratini` and
every one of those Pokémon's TCGCSV product SKUs (which include
per-print single cards) landed in the `products` table alongside real
sealed items. Also: `Prerelease` single-card SKUs ("Victini - 43/101
(Prerelease) [Staff]") snuck in via the ambiguous "prerelease" hint
that was meant for prerelease KITS.

This script re-runs the CORRECTED `_looks_sealed` over every existing
product row and deletes the ones that fail. Safe to run repeatedly —
idempotent. Cascading deletes clean up related snapshots + wishlist +
collection rows via FK ON DELETE CASCADE.

Usage:
    python -m scripts.cleanup_false_positive_products --dry-run
    python -m scripts.cleanup_false_positive_products
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.database import SessionLocal, init_db
from app.models import Product
from scripts.ingest_products import _looks_sealed


async def run(dry_run: bool) -> None:
    await init_db()
    async with SessionLocal() as db:
        rows = (
            await db.execute(select(Product.id, Product.name))
        ).all()

    doomed: list[tuple[str, str]] = [
        (pid, name) for pid, name in rows if not _looks_sealed(name)
    ]
    kept = len(rows) - len(doomed)

    print(f"scanned: {len(rows)} products")
    print(f"kept:    {kept}")
    print(f"doomed:  {len(doomed)}")
    print("--- sample doomed (first 30) ---")
    for pid, name in doomed[:30]:
        print(f"  {pid:12} {name[:70]}")

    if dry_run:
        print("\n--dry-run: no deletes performed")
        return

    if not doomed:
        print("nothing to delete")
        return

    doomed_ids = [pid for pid, _ in doomed]
    BATCH = 500
    async with SessionLocal() as db2:
        for i in range(0, len(doomed_ids), BATCH):
            chunk = doomed_ids[i : i + BATCH]
            await db2.execute(
                delete(Product).where(Product.id.in_(chunk))
            )
        await db2.commit()
    print(f"\ndeleted {len(doomed_ids)} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
