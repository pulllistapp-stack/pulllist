"""Move the 30th-Celebration 094-110 promos from set_id='mep' back to 'me30'.

Previous seed put these under mep as generic promos, but LO's pokecottage
sourced list shows they're actually part of the 30th Celebration set —
which needs to display 38 cards total.

Run once, idempotent (safe to re-run: WHERE clause is number-scoped).
"""
import asyncio

from sqlalchemy import select, update, func, and_
from app.database import SessionLocal
from app.models.card import Card


TARGET_NUMBERS = [str(n).zfill(3) for n in range(94, 111)] + [str(n) for n in range(94, 111)]


async def main() -> None:
    async with SessionLocal() as db:
        before_mep = (await db.execute(
            select(func.count()).select_from(Card).where(Card.set_id == "mep")
        )).scalar()
        before_me30 = (await db.execute(
            select(func.count()).select_from(Card).where(Card.set_id == "me30")
        )).scalar()

        rows = (await db.execute(
            select(Card.id, Card.number, Card.name)
            .where(and_(Card.set_id == "mep", Card.number.in_(TARGET_NUMBERS)))
            .order_by(Card.number_int)
        )).all()
        print(f"[before] mep={before_mep}  me30={before_me30}")
        print(f"[move]   {len(rows)} rows queued")
        for r in rows:
            print(f"           {r.number:>4}  {r.name}")

        if not rows:
            print("nothing to move — done.")
            return

        ids = [r.id for r in rows]
        await db.execute(
            update(Card).where(Card.id.in_(ids)).values(set_id="me30")
        )
        await db.commit()

        after_mep = (await db.execute(
            select(func.count()).select_from(Card).where(Card.set_id == "mep")
        )).scalar()
        after_me30 = (await db.execute(
            select(func.count()).select_from(Card).where(Card.set_id == "me30")
        )).scalar()
        print(f"[after]  mep={after_mep}  me30={after_me30}")


if __name__ == "__main__":
    asyncio.run(main())
