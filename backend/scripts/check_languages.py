"""Inspect what languages/regions our catalog actually covers."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, or_, select

from app.database import SessionLocal
from app.models import Card, Set


KEYWORDS_JP = ["Japanese", "Japan", "JP", "Pokemon Card"]
KEYWORDS_PROMO = ["Promo", "Black Star", "Holon"]


async def main() -> None:
    async with SessionLocal() as db:
        total_sets = (await db.execute(select(func.count(Set.id)))).scalar_one()
        print(f"Total sets: {total_sets}\n")

        # Probably-Japanese sets (by name)
        print("=== Sets with JP-suggesting names ===")
        stmt = select(Set.id, Set.name, Set.series).where(
            or_(*[Set.name.ilike(f"%{k}%") for k in KEYWORDS_JP])
        )
        for sid, name, series in (await db.execute(stmt)).all():
            print(f"  {sid:15} {name:45} ({series})")

        # Check series list for non-Western patterns
        print("\n=== Distinct series ===")
        for (series,) in (
            await db.execute(select(Set.series).distinct().order_by(Set.series))
        ).all():
            n = (
                await db.execute(
                    select(func.count(Set.id)).where(Set.series == series)
                )
            ).scalar_one()
            print(f"  {series or '(null)':30}  {n} sets")

        # Sample of cards with non-English suggesting names
        print("\n=== Cards with explicit JP markers in name ===")
        stmt = (
            select(Card.id, Card.name, Set.name)
            .join(Set, Card.set_id == Set.id)
            .where(
                or_(
                    Card.name.ilike("%(Japanese)%"),
                    Card.name.ilike("%JP %"),
                    Card.name.ilike("%リザードン%"),  # Japanese for Charizard
                    Card.name.ilike("%ピカチュウ%"),  # Pikachu in JP
                )
            )
            .limit(20)
        )
        rows = (await db.execute(stmt)).all()
        if rows:
            for cid, cname, sname in rows:
                print(f"  {cid:15} {cname:35} ({sname})")
        else:
            print("  (none — all card names appear English)")


if __name__ == "__main__":
    asyncio.run(main())
