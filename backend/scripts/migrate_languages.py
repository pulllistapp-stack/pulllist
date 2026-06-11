"""Add language + name_local + parent_id columns to sets and cards.

Idempotent: safe to re-run.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


COLUMNS_TO_ADD = {
    "sets": [
        ("language", "VARCHAR(8) NOT NULL DEFAULT 'en'"),
        ("name_local", "VARCHAR(255)"),
        ("parent_set_id", "VARCHAR(64)"),
    ],
    "cards": [
        ("language", "VARCHAR(8) NOT NULL DEFAULT 'en'"),
        ("name_local", "VARCHAR(255)"),
        ("parent_card_id", "VARCHAR(64)"),
    ],
}

INDEXES_TO_CREATE = [
    ("ix_sets_language", "sets", "language"),
    ("ix_sets_parent_set_id", "sets", "parent_set_id"),
    ("ix_cards_language", "cards", "language"),
    ("ix_cards_parent_card_id", "cards", "parent_card_id"),
]


async def column_exists(conn, table: str, column: str) -> bool:
    rows = await conn.execute(text(f"PRAGMA table_info({table})"))
    return any(r[1] == column for r in rows.fetchall())


async def main() -> None:
    async with engine.begin() as conn:
        for table, cols in COLUMNS_TO_ADD.items():
            for col_name, col_type in cols:
                if await column_exists(conn, table, col_name):
                    print(f"  {table}.{col_name} already exists, skip.")
                    continue
                print(f"  Adding {table}.{col_name}…")
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                )

        for idx_name, table, column in INDEXES_TO_CREATE:
            print(f"  Creating index {idx_name}…")
            await conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})"
                )
            )

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
