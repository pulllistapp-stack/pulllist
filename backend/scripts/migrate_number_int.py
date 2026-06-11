"""Add `number_int` column to cards + backfill from `number`.

Idempotent: skips ALTER if column already exists, re-runs UPDATE safely.
"""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text, update

from app.database import SessionLocal, engine
from app.models import Card

_NUMBER_PREFIX = re.compile(r"^(\d+)")


def parse_card_number(value: str | None) -> int | None:
    if not value:
        return None
    m = _NUMBER_PREFIX.match(value)
    return int(m.group(1)) if m else None


async def column_exists(conn, table: str, column: str) -> bool:
    rows = await conn.execute(text(f"PRAGMA table_info({table})"))
    return any(r[1] == column for r in rows.fetchall())


async def main() -> None:
    async with engine.begin() as conn:
        if await column_exists(conn, "cards", "number_int"):
            print("Column number_int already exists, skipping ALTER.")
        else:
            print("Adding column number_int...")
            await conn.execute(text("ALTER TABLE cards ADD COLUMN number_int INTEGER"))
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_cards_number_int ON cards (number_int)")
            )

    async with SessionLocal() as db:
        cards = (await db.execute(select(Card.id, Card.number))).all()
        print(f"Backfilling {len(cards)} cards...")
        updated = 0
        for cid, number in cards:
            value = parse_card_number(number)
            await db.execute(
                update(Card).where(Card.id == cid).values(number_int=value)
            )
            updated += 1
            if updated % 2000 == 0:
                print(f"  {updated}/{len(cards)}")
                await db.commit()
        await db.commit()
        print(f"Backfilled {updated} rows.")


if __name__ == "__main__":
    asyncio.run(main())
