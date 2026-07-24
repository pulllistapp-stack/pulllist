"""Add bot_name VARCHAR(64) column to visit_logs.

Idempotent: safe to re-run — checks information_schema for the column
first and skips if already present.

Usage:
    python -m scripts.migrate_add_bot_name --dry-run
    python -m scripts.migrate_add_bot_name
"""

import argparse
import asyncio

from sqlalchemy import text

from app.database import engine


async def _column_exists(conn) -> bool:
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'visit_logs' AND column_name = 'bot_name'"
        )
    )
    return result.fetchone() is not None


async def main(dry_run: bool) -> None:
    async with engine.begin() as conn:
        if await _column_exists(conn):
            print("bot_name column already exists on visit_logs — nothing to do.")
            return

        stmt = "ALTER TABLE visit_logs ADD COLUMN bot_name VARCHAR(64)"
        if dry_run:
            print(f"[dry-run] Would execute: {stmt}")
            return

        await conn.execute(text(stmt))
        print("Added bot_name column to visit_logs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the ALTER statement without executing.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
