"""Add cards.hp_int + backfill from cards.hp. Idempotent."""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text, update

from app.database import SessionLocal, engine
from app.models import Card

_HP_PREFIX = re.compile(r"^(\d+)")


def parse_hp(value: str | None) -> int | None:
    if not value:
        return None
    m = _HP_PREFIX.match(value)
    return int(m.group(1)) if m else None


async def column_exists(conn, table: str, column: str) -> bool:
    rows = await conn.execute(text(f"PRAGMA table_info({table})"))
    return any(r[1] == column for r in rows.fetchall())


async def main() -> None:
    async with engine.begin() as conn:
        if await column_exists(conn, "cards", "hp_int"):
            print("Column cards.hp_int already exists.")
        else:
            print("Adding cards.hp_int…")
            await conn.execute(text("ALTER TABLE cards ADD COLUMN hp_int INTEGER"))
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_cards_hp_int ON cards (hp_int)")
            )

    async with SessionLocal() as db:
        cards = (await db.execute(select(Card.id, Card.hp))).all()
        print(f"Backfilling {len(cards)} cards…")
        updated = 0
        for cid, hp in cards:
            await db.execute(update(Card).where(Card.id == cid).values(hp_int=parse_hp(hp)))
            updated += 1
            if updated % 2000 == 0:
                print(f"  {updated}/{len(cards)}")
                await db.commit()
        await db.commit()
        print(f"Backfilled {updated} rows.")


if __name__ == "__main__":
    asyncio.run(main())
