"""Collection routes — owned cards, completion %, totals.

All routes require a valid JWT (user dependency).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Card, CollectionItem, Set, User
from app.schemas.collection import (
    CollectionItemCreate,
    CollectionItemDetail,
    CollectionItemRead,
    CollectionItemUpdate,
    SetCompletion,
)

router = APIRouter(prefix="/collection", tags=["collection"])


@router.get("/items", response_model=list[CollectionItemDetail])
async def list_my_items(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    set_id: str | None = Query(None),
) -> list[CollectionItemDetail]:
    stmt = (
        select(CollectionItem, Card, Set.name)
        .join(Card, CollectionItem.card_id == Card.id)
        .join(Set, Card.set_id == Set.id)
        .where(CollectionItem.user_id == user.id)
        .order_by(CollectionItem.created_at.desc())
    )
    if set_id:
        stmt = stmt.where(Card.set_id == set_id)

    rows = (await db.execute(stmt)).all()
    return [
        CollectionItemDetail(
            **CollectionItemRead.model_validate(item).model_dump(),
            card_name=card.name,
            card_number=card.number,
            image_small=card.image_small,
            rarity=card.rarity,
            market_price_usd=card.market_price_usd,
            set_id=card.set_id,
            set_name=set_name,
        )
        for item, card, set_name in rows
    ]


@router.post("/items", response_model=CollectionItemRead, status_code=status.HTTP_201_CREATED)
async def add_item(
    payload: CollectionItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionItemRead:
    card = await db.get(Card, payload.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # If an identical (user, card, variant) row exists, increment qty instead
    existing = (
        await db.execute(
            select(CollectionItem).where(
                CollectionItem.user_id == user.id,
                CollectionItem.card_id == payload.card_id,
                CollectionItem.condition == payload.condition,
                CollectionItem.is_graded == payload.is_graded,
                CollectionItem.grade == payload.grade,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.qty = min(999, existing.qty + payload.qty)
        await db.commit()
        await db.refresh(existing)
        return CollectionItemRead.model_validate(existing)

    item = CollectionItem(
        user_id=user.id,
        card_id=payload.card_id,
        qty=payload.qty,
        condition=payload.condition,
        is_graded=payload.is_graded,
        grade=payload.grade,
        acquired_at=payload.acquired_at,
        notes=payload.notes,
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate entry")
    await db.refresh(item)
    return CollectionItemRead.model_validate(item)


@router.patch("/items/{item_id}", response_model=CollectionItemRead)
async def update_item(
    item_id: int,
    payload: CollectionItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionItemRead:
    item = await db.get(CollectionItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return CollectionItemRead.model_validate(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    item = await db.get(CollectionItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()


@router.get("/cards/{card_id}", response_model=list[CollectionItemRead])
async def get_card_entries(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollectionItemRead]:
    """All my entries for a specific card (different conditions/grades)."""
    rows = (
        await db.execute(
            select(CollectionItem).where(
                CollectionItem.user_id == user.id,
                CollectionItem.card_id == card_id,
            )
        )
    ).scalars().all()
    return [CollectionItemRead.model_validate(r) for r in rows]


@router.post("/cards/{card_id}/toggle", response_model=dict)
async def toggle_card_owned(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """One-click toggle — adds a default NM entry if none exists, else removes
    all entries for this (user, card). Used by the 'I have this' button."""
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    existing = (
        await db.execute(
            select(CollectionItem).where(
                CollectionItem.user_id == user.id,
                CollectionItem.card_id == card_id,
            )
        )
    ).scalars().all()

    if existing:
        for item in existing:
            await db.delete(item)
        await db.commit()
        return {"owned": False}

    item = CollectionItem(
        user_id=user.id,
        card_id=card_id,
        qty=1,
        condition="NM",
        is_graded=False,
        grade=None,
    )
    db.add(item)
    await db.commit()
    return {"owned": True}


@router.get("/owned-ids", response_model=list[str])
async def list_owned_card_ids(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    set_id: str | None = Query(None),
) -> list[str]:
    """Bulk endpoint — returns just card IDs the user owns. Used by frontend
    to highlight owned cards in grids without N round-trips."""
    stmt = (
        select(CollectionItem.card_id)
        .where(CollectionItem.user_id == user.id)
        .distinct()
    )
    if set_id:
        stmt = stmt.join(Card, CollectionItem.card_id == Card.id).where(
            Card.set_id == set_id
        )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


@router.get("/sets/{set_id}/completion", response_model=SetCompletion)
async def set_completion(
    set_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SetCompletion:
    set_row = await db.get(Set, set_id)
    if not set_row:
        raise HTTPException(status_code=404, detail="Set not found")

    total = (
        await db.execute(select(func.count(Card.id)).where(Card.set_id == set_id))
    ).scalar_one()

    stmt = (
        select(
            func.count(func.distinct(CollectionItem.card_id)).label("unique"),
            func.coalesce(func.sum(CollectionItem.qty), 0).label("total_qty"),
            func.coalesce(
                func.sum(
                    case(
                        (Card.market_price_usd.is_not(None),
                         CollectionItem.qty * Card.market_price_usd),
                        else_=0,
                    )
                ),
                0,
            ).label("value"),
        )
        .join(Card, CollectionItem.card_id == Card.id)
        .where(CollectionItem.user_id == user.id, Card.set_id == set_id)
    )
    row = (await db.execute(stmt)).one()

    return SetCompletion(
        set_id=set_id,
        set_name=set_row.name,
        total_cards=total,
        owned_unique=row.unique or 0,
        owned_total_qty=row.total_qty or 0,
        completion_pct=round((row.unique or 0) / total * 100, 1) if total else 0.0,
        estimated_value_usd=round(float(row.value or 0), 2),
    )


@router.get("/summary", response_model=dict)
async def my_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """High-level stats for the user's whole collection."""
    stmt = (
        select(
            func.count(CollectionItem.id).label("total_entries"),
            func.count(func.distinct(CollectionItem.card_id)).label("unique_cards"),
            func.coalesce(func.sum(CollectionItem.qty), 0).label("total_qty"),
            func.coalesce(
                func.sum(
                    case(
                        (Card.market_price_usd.is_not(None),
                         CollectionItem.qty * Card.market_price_usd),
                        else_=0,
                    )
                ),
                0,
            ).label("value"),
            func.count(func.distinct(Card.set_id)).label("sets_touched"),
        )
        .join(Card, CollectionItem.card_id == Card.id)
        .where(CollectionItem.user_id == user.id)
    )
    row = (await db.execute(stmt)).one()
    return {
        "total_entries": row.total_entries or 0,
        "unique_cards": row.unique_cards or 0,
        "total_qty": int(row.total_qty or 0),
        "sets_touched": row.sets_touched or 0,
        "estimated_value_usd": round(float(row.value or 0), 2),
    }
