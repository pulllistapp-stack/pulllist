import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Card, Set


async def main() -> None:
    async with SessionLocal() as db:
        total_sets = (await db.execute(select(func.count(Set.id)))).scalar_one()
        total_cards = (await db.execute(select(func.count(Card.id)))).scalar_one()
        print(f"Sets: {total_sets}")
        print(f"Cards: {total_cards}")
        print()

        rows = await db.execute(
            select(Card.set_id, func.count(Card.id))
            .group_by(Card.set_id)
            .order_by(func.count(Card.id).desc())
            .limit(10)
        )
        print("Top 10 sets by card count:")
        for set_id, count in rows.all():
            print(f"  {set_id}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
