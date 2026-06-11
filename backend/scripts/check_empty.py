import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Card, Set


async def main() -> None:
    async with SessionLocal() as db:
        rows = await db.execute(
            select(Set.id, Set.name, Set.total, func.count(Card.id))
            .outerjoin(Card, Card.set_id == Set.id)
            .group_by(Set.id)
            .having(func.count(Card.id) == 0)
            .order_by(Set.release_date.desc().nullslast())
        )
        empty = rows.all()
        print(f"Empty sets: {len(empty)}\n")
        for set_id, name, total, count in empty:
            print(f"  {set_id:20} {name:40}  total={total}")


if __name__ == "__main__":
    asyncio.run(main())
