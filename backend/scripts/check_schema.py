"""Print full schema of all tables for verification."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


async def main() -> None:
    async with engine.begin() as conn:
        tables = (
            await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
        ).fetchall()
        for (name,) in tables:
            if name.startswith("sqlite_"):
                continue
            print(f"\n=== {name} ===")
            cols = (await conn.execute(text(f"PRAGMA table_info({name})"))).fetchall()
            for col in cols:
                _, col_name, col_type, notnull, default, pk = col
                pk_mark = " [PK]" if pk else ""
                nn_mark = " NOT NULL" if notnull else ""
                default_mark = f" DEFAULT {default}" if default else ""
                print(f"  {col_name:25} {col_type:20}{nn_mark}{default_mark}{pk_mark}")


if __name__ == "__main__":
    asyncio.run(main())
