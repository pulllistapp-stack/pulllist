"""Test Postgres connection."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


async def main() -> None:
    async with engine.begin() as conn:
        version = (await conn.execute(text("SELECT version()"))).scalar_one()
        print("Postgres version:")
        print(" ", version)
        print()
        db = (await conn.execute(text("SELECT current_database()"))).scalar_one()
        user = (await conn.execute(text("SELECT current_user"))).scalar_one()
        print(f"Connected as: {user} @ {db}")
        print("OK")


if __name__ == "__main__":
    asyncio.run(main())
