"""Wishlist routes — cards the user wants to acquire.

Sister surface to /collection. Where the collection tracks what you own, the
wishlist tracks what you'd love to find next — optionally with a target price
ceiling so future price-alert logic knows when to ping.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Card, Set, User, WishlistItem

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


# ────────── schemas ──────────


class WishlistItemRead(BaseModel):
    id: int
    card_id: str
    priority: int
    max_price_usd: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WishlistItemDetail(WishlistItemRead):
    card_name: str
    card_number: Optional[str] = None
    image_small: Optional[str] = None
    rarity: Optional[str] = None
    market_price_usd: Optional[float] = None
    set_id: str
    set_name: str
    # True when the current market price already meets the user's target.
    target_met: bool = False


class WishlistItemCreate(BaseModel):
    card_id: str
    priority: int = Field(3, ge=1, le=5)
    max_price_usd: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)


class WishlistItemUpdate(BaseModel):
    priority: Optional[int] = Field(None, ge=1, le=5)
    max_price_usd: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)


# ────────── endpoints ──────────


@router.get("/items", response_model=list[WishlistItemDetail])
async def list_my_wishlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    set_id: str | None = Query(None),
    only_target_met: bool = Query(
        False,
        description="When true, only return cards whose market price is at or below the user's max_price_usd.",
    ),
) -> list[WishlistItemDetail]:
    stmt = (
        select(WishlistItem, Card, Set.name)
        .join(Card, WishlistItem.card_id == Card.id)
        .join(Set, Card.set_id == Set.id)
        .where(WishlistItem.user_id == user.id)
        .order_by(
            WishlistItem.priority.desc(),
            WishlistItem.created_at.desc(),
        )
    )
    if set_id:
        stmt = stmt.where(Card.set_id == set_id)

    rows = (await db.execute(stmt)).all()
    out: list[WishlistItemDetail] = []
    for item, card, set_name in rows:
        target_met = (
            item.max_price_usd is not None
            and card.market_price_usd is not None
            and float(card.market_price_usd) <= float(item.max_price_usd)
        )
        if only_target_met and not target_met:
            continue
        base = WishlistItemRead.model_validate(item).model_dump()
        out.append(
            WishlistItemDetail(
                **base,
                card_name=card.name,
                card_number=card.number,
                image_small=card.image_small,
                rarity=card.rarity,
                market_price_usd=float(card.market_price_usd)
                if card.market_price_usd is not None
                else None,
                set_id=card.set_id,
                set_name=set_name,
                target_met=target_met,
            )
        )
    return out


@router.get("/ids", response_model=list[str])
async def list_wishlist_card_ids(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Bulk endpoint — returns just card IDs the user has wishlisted. Used by
    the frontend to highlight wishlist hearts on card grids without N RTTs."""
    rows = (
        await db.execute(
            select(WishlistItem.card_id).where(WishlistItem.user_id == user.id)
        )
    ).scalars().all()
    return list(rows)


@router.post("/items", response_model=WishlistItemRead, status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    payload: WishlistItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WishlistItemRead:
    card = await db.get(Card, payload.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    item = WishlistItem(
        user_id=user.id,
        card_id=payload.card_id,
        priority=payload.priority,
        max_price_usd=payload.max_price_usd,
        notes=payload.notes,
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already on your wishlist")
    await db.refresh(item)
    return WishlistItemRead.model_validate(item)


@router.patch("/items/{item_id}", response_model=WishlistItemRead)
async def update_wishlist_item(
    item_id: int,
    payload: WishlistItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WishlistItemRead:
    item = await db.get(WishlistItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return WishlistItemRead.model_validate(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wishlist_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    item = await db.get(WishlistItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()


@router.post("/cards/{card_id}/toggle", response_model=dict)
async def toggle_wishlist(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """One-click toggle — adds with default priority=3 if not on wishlist,
    removes if already there. Used by the heart icon on card thumbnails."""
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    existing = (
        await db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == user.id,
                WishlistItem.card_id == card_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"wishlisted": False}

    item = WishlistItem(
        user_id=user.id,
        card_id=card_id,
        priority=3,
    )
    db.add(item)
    await db.commit()
    return {"wishlisted": True}


@router.get("/summary", response_model=dict)
async def wishlist_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """High-level stats for the wishlist (count, est. total cost, # at target)."""
    stmt = (
        select(
            func.count(WishlistItem.id).label("total"),
            func.coalesce(
                func.sum(
                    case(
                        (Card.market_price_usd.is_not(None), Card.market_price_usd),
                        else_=0,
                    )
                ),
                0,
            ).label("est_value"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (WishlistItem.max_price_usd.is_not(None))
                            & (Card.market_price_usd.is_not(None))
                            & (Card.market_price_usd <= WishlistItem.max_price_usd),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("at_target"),
        )
        .join(Card, WishlistItem.card_id == Card.id)
        .where(WishlistItem.user_id == user.id)
    )
    row = (await db.execute(stmt)).one()
    return {
        "total": row.total or 0,
        "estimated_value_usd": round(float(row.est_value or 0), 2),
        "at_target_count": int(row.at_target or 0),
    }
