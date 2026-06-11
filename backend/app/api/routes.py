from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Card, CardPriceSnapshot, Set
from app.schemas.card import CardList, CardRead
from app.schemas.set import SetRead, SetWithCardCount

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/sets", response_model=list[SetWithCardCount])
async def list_sets(
    db: AsyncSession = Depends(get_db),
    series: str | None = Query(None, description="Filter by series name"),
) -> list[SetWithCardCount]:
    stmt = (
        select(Set, func.count(Card.id).label("card_count"))
        .outerjoin(Card, Card.set_id == Set.id)
        .group_by(Set.id)
        .order_by(Set.release_date.desc().nullslast())
    )
    if series:
        stmt = stmt.where(Set.series == series)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        SetWithCardCount(
            **SetRead.model_validate(set_row).model_dump(),
            card_count=count,
        )
        for set_row, count in rows
    ]


@router.get("/sets/{set_id}", response_model=SetWithCardCount)
async def get_set(
    set_id: str, db: AsyncSession = Depends(get_db)
) -> SetWithCardCount:
    stmt = (
        select(Set, func.count(Card.id).label("card_count"))
        .outerjoin(Card, Card.set_id == Set.id)
        .where(Set.id == set_id)
        .group_by(Set.id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Set not found")
    set_row, count = row
    return SetWithCardCount(
        **SetRead.model_validate(set_row).model_dump(),
        card_count=count,
    )


def _card_to_read(
    card: Card,
    set_name: str | None,
    set_printed_total: int | None = None,
    set_ptcgo_code: str | None = None,
) -> CardRead:
    data = CardRead.model_validate(card).model_dump()
    data["set_name"] = set_name
    data["set_printed_total"] = set_printed_total
    data["set_ptcgo_code"] = set_ptcgo_code
    return CardRead(**data)


@router.get("/sets/{set_id}/cards", response_model=CardList)
async def list_cards_in_set(
    set_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=250),
) -> CardList:
    offset = (page - 1) * page_size

    set_row = await db.get(Set, set_id)
    if not set_row:
        raise HTTPException(status_code=404, detail="Set not found")

    total_stmt = select(func.count(Card.id)).where(Card.set_id == set_id)
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(Card)
        .where(Card.set_id == set_id)
        .order_by(
            Card.number_int.is_(None),
            Card.number_int,
            Card.number,
        )
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    cards = result.scalars().all()

    return CardList(
        items=[
            _card_to_read(
                c, set_row.name, set_row.printed_total, set_row.ptcgo_code
            )
            for c in cards
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cards/search", response_model=CardList)
async def search_cards(
    q: str = Query(..., min_length=1, description="Search query"),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> CardList:
    offset = (page - 1) * page_size
    pattern = f"%{q}%"

    total_stmt = select(func.count(Card.id)).where(Card.name.ilike(pattern))
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(Card, Set.name, Set.printed_total, Set.ptcgo_code)
        .join(Set, Card.set_id == Set.id)
        .where(Card.name.ilike(pattern))
        .order_by(
            Card.market_price_usd.desc().nullslast(),
            Card.name,
        )
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    return CardList(
        items=[
            _card_to_read(c, sname, ptot, pcode)
            for c, sname, ptot, pcode in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cards/suggest")
async def suggest_cards(
    q: str = Query(..., min_length=1, description="Autocomplete query"),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(8, ge=1, le=20),
) -> list[dict]:
    pattern = f"{q}%"
    pattern_contains = f"%{q}%"

    stmt = (
        select(Card, Set.name)
        .join(Set, Card.set_id == Set.id)
        .where(Card.name.ilike(pattern_contains))
        .order_by(
            Card.name.ilike(pattern).desc(),
            Card.market_price_usd.desc().nullslast(),
            Card.name,
        )
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "number": c.number,
            "set_id": c.set_id,
            "set_name": set_name,
            "image_small": c.image_small,
            "rarity": c.rarity,
            "market_price_usd": c.market_price_usd,
        }
        for c, set_name in rows
    ]


@router.get("/cards/{card_id}/alternates", response_model=list[CardRead])
async def list_alternates(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(12, ge=1, le=50),
) -> list[CardRead]:
    base = await db.get(Card, card_id)
    if not base:
        raise HTTPException(status_code=404, detail="Card not found")

    stmt = (
        select(Card, Set.name, Set.printed_total, Set.ptcgo_code)
        .join(Set, Card.set_id == Set.id)
        .where(Card.name == base.name, Card.id != base.id)
        .order_by(Set.release_date.desc().nullslast(), Card.number_int.asc().nullslast())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        _card_to_read(c, sname, ptot, pcode)
        for c, sname, ptot, pcode in rows
    ]


@router.get("/cards/{card_id}/history")
async def get_card_history(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    source: str | None = Query(None, description="Filter by source (e.g. tcgplayer)"),
    variant: str | None = Query(None, description="Filter by variant (e.g. holofoil)"),
) -> dict:
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    cutoff = (date.today() - timedelta(days=days)).isoformat()

    stmt = (
        select(CardPriceSnapshot)
        .where(
            CardPriceSnapshot.card_id == card_id,
            CardPriceSnapshot.snapshot_date >= cutoff,
        )
        .order_by(CardPriceSnapshot.snapshot_date.asc())
    )
    if source:
        stmt = stmt.where(CardPriceSnapshot.source == source)
    if variant:
        stmt = stmt.where(CardPriceSnapshot.variant == variant)

    rows = (await db.execute(stmt)).scalars().all()

    series: dict[str, list[dict]] = {}
    for r in rows:
        key = f"{r.source}:{r.variant}"
        series.setdefault(key, []).append(
            {
                "date": r.snapshot_date,
                "market": r.market_price_usd,
                "low": r.low_price_usd,
                "mid": r.mid_price_usd,
                "high": r.high_price_usd,
                "sales": r.sales_count,
            }
        )

    return {
        "card_id": card_id,
        "card_name": card.name,
        "days": days,
        "series_count": len(series),
        "series": series,
    }


@router.get("/cards/{card_id}", response_model=CardRead)
async def get_card(card_id: str, db: AsyncSession = Depends(get_db)) -> CardRead:
    stmt = (
        select(Card, Set.name, Set.printed_total, Set.ptcgo_code)
        .join(Set, Card.set_id == Set.id)
        .where(Card.id == card_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Card not found")
    card, set_name, set_printed_total, set_ptcgo_code = row
    return _card_to_read(card, set_name, set_printed_total, set_ptcgo_code)
