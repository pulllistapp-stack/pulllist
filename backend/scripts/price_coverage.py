import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import case, func, select

from app.database import SessionLocal
from app.models import Card, Set


async def main() -> None:
    async with SessionLocal() as db:
        stmt = (
            select(
                Set.id,
                Set.name,
                Set.release_date,
                func.count(Card.id).label("total"),
                func.sum(case((Card.market_price_usd.is_not(None), 1), else_=0)).label("priced"),
            )
            .join(Card, Card.set_id == Set.id)
            .group_by(Set.id)
            .order_by(Set.release_date.desc().nullslast())
            .limit(15)
        )
        rows = (await db.execute(stmt)).all()
        print(f"{'Set':<35} {'Release':<12} {'Priced/Total':<15} {'Coverage'}")
        print("-" * 80)
        for set_id, name, release, total, priced in rows:
            pct = (priced / total * 100) if total else 0
            name_short = (name[:33] + "..") if len(name) > 33 else name
            print(
                f"{name_short:<35} {str(release):<12} {priced}/{total:<10} {pct:5.1f}%"
            )


if __name__ == "__main__":
    asyncio.run(main())
