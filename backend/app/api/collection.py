"""Collection routes — owned cards, completion %, totals.

All routes require a valid JWT (user dependency).
"""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Card, CollectionItem, PortfolioSnapshot, Set, User
from app.schemas.collection import (
    CollectionItemCreate,
    CollectionItemDetail,
    CollectionItemRead,
    CollectionItemUpdate,
    SetCompletion,
)
from app.services.variant_pricing import price_for_variant

router = APIRouter(prefix="/collection", tags=["collection"])


@router.get("/export.csv")
async def export_collection_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Stream the caller's full collection as a CSV download.

    One row per CollectionItem (a (card, condition) pair the user owns),
    sorted by set then card number so the file opens cleanly in Excel /
    Google Sheets. Total value column = qty × market_price_usd; rows
    without a market price get total_value_usd blank.
    """
    stmt = (
        select(CollectionItem, Card, Set.name)
        .join(Card, CollectionItem.card_id == Card.id)
        .join(Set, Card.set_id == Set.id)
        .where(CollectionItem.user_id == user.id)
        .order_by(Set.name.asc(), Card.number_int.asc().nullslast(), Card.number.asc())
    )
    rows = (await db.execute(stmt)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "card_id",
            "name",
            "set_name",
            "number",
            "rarity",
            "variant",
            "condition",
            "qty",
            "market_price_usd",
            "total_value_usd",
            "purchase_price_usd",
            "notes",
            "added_at",
        ]
    )
    for item, card, set_name in rows:
        # Variant-specific market price — reverseHolofoil entry priced
        # at reverse-holo's $34.67, normal at $0.50.
        price = price_for_variant(
            card.tcgplayer_prices, item.variant, card.market_price_usd
        )
        qty = item.qty or 0
        total = f"{price * qty:.2f}" if price is not None else ""
        writer.writerow(
            [
                card.id,
                card.name,
                set_name,
                card.number or "",
                card.rarity or "",
                item.variant or "normal",
                item.condition or "",
                qty,
                f"{price:.2f}" if price is not None else "",
                total,
                f"{float(item.purchase_price_usd):.2f}" if getattr(item, "purchase_price_usd", None) is not None else "",
                (item.notes or "").replace("\n", " ").strip(),
                item.created_at.date().isoformat() if item.created_at else "",
            ]
        )

    csv_text = buf.getvalue()
    today = date.today().isoformat()
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="pulllist-collection-{today}.csv"',
            "Cache-Control": "no-store",
        },
    )


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
            # Variant-aware: use the price for THIS user's specific
            # variant of THIS card (reverseHolofoil Larvitar $34.67 vs
            # normal $0.50). Falls back to card.market_price_usd if the
            # tcgplayer_prices JSON doesn't have that variant.
            market_price_usd=price_for_variant(
                card.tcgplayer_prices, item.variant, card.market_price_usd
            ),
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

    # If an identical (user, card, variant, condition, grade) row
    # exists, increment qty instead.
    existing = (
        await db.execute(
            select(CollectionItem).where(
                CollectionItem.user_id == user.id,
                CollectionItem.card_id == payload.card_id,
                CollectionItem.variant == payload.variant,
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
        variant=payload.variant,
        condition=payload.condition,
        is_graded=payload.is_graded,
        grade=payload.grade,
        acquired_at=payload.acquired_at,
        notes=payload.notes,
        purchase_price_usd=payload.purchase_price_usd,
        acquisition_type=payload.acquisition_type,
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


class _BulkDeleteIn(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)


@router.post("/items/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def remove_items_bulk(
    payload: _BulkDeleteIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete N collection items in one round-trip.

    The Portfolio "Manage" mode hands us the selected ids; without this
    endpoint a 50-card cleanup is 50 sequential DELETEs over the network.
    Scopes the WHERE to the caller's user_id so a stray id from another
    user can't leak through, and silently skips ids that don't match
    (no 404 — the frontend already optimistically clears the rows).
    """
    await db.execute(
        delete(CollectionItem).where(
            CollectionItem.id.in_(payload.ids),
            CollectionItem.user_id == user.id,
        )
    )
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
    variant: str = Query("normal", pattern=r"^(normal|holofoil|reverseHolofoil|1stEdition|1stEditionHolofoil|unlimited|unlimitedHolofoil)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """One-click toggle — adds a default NM entry of `variant` (default
    'normal') if none exists for that specific variant, else removes
    all that variant's entries. Other variants of the same card stay
    untouched, so toggling normal Larvitar doesn't delete the user's
    reverseHolofoil Larvitar."""
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    existing = (
        await db.execute(
            select(CollectionItem).where(
                CollectionItem.user_id == user.id,
                CollectionItem.card_id == card_id,
                CollectionItem.variant == variant,
            )
        )
    ).scalars().all()

    if existing:
        for item in existing:
            await db.delete(item)
        await db.commit()
        return {"owned": False, "variant": variant}

    item = CollectionItem(
        user_id=user.id,
        card_id=card_id,
        qty=1,
        variant=variant,
        condition="NM",
        is_graded=False,
        grade=None,
    )
    db.add(item)
    await db.commit()
    return {"owned": True, "variant": variant}


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

    # Variant-aware value: walk items in Python and look up each one's
    # per-variant price from card.tcgplayer_prices. SQL can't easily
    # index into the JSON for the right variant.
    rows = (
        await db.execute(
            select(
                CollectionItem.qty,
                CollectionItem.variant,
                Card.tcgplayer_prices,
                Card.market_price_usd,
                CollectionItem.card_id,
            )
            .join(Card, CollectionItem.card_id == Card.id)
            .where(CollectionItem.user_id == user.id, Card.set_id == set_id)
        )
    ).all()

    unique_ids: set[str] = set()
    total_qty = 0
    value = 0.0
    for qty, variant, prices, fallback, card_id in rows:
        unique_ids.add(card_id)
        total_qty += qty or 0
        p = price_for_variant(prices, variant, fallback)
        if p is not None:
            value += (qty or 0) * p

    return SetCompletion(
        set_id=set_id,
        set_name=set_row.name,
        total_cards=total,
        owned_unique=len(unique_ids),
        owned_total_qty=total_qty,
        completion_pct=round(len(unique_ids) / total * 100, 1) if total else 0.0,
        estimated_value_usd=round(value, 2),
    )


@router.get("/portfolio/history", response_model=dict)
async def portfolio_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    period_days: int = Query(
        30,
        ge=1,
        le=365,
        description="How many days of history to return.",
    ),
) -> dict:
    """Time-series of the user's portfolio valuation.

    Returns one row per day snapshot the cron has captured. Frontend uses
    this to render the Growth chart on /portfolio.
    """
    from datetime import date as date_cls, timedelta

    cutoff = (date_cls.today() - timedelta(days=period_days)).isoformat()
    rows = (
        await db.execute(
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.user_id == user.id,
                PortfolioSnapshot.snapshot_date >= cutoff,
            )
            .order_by(PortfolioSnapshot.snapshot_date.asc())
        )
    ).scalars().all()

    points = [
        {
            "date": r.snapshot_date,
            "value": round(float(r.estimated_value_usd), 2),
            "unique_cards": r.unique_cards,
            "total_qty": r.total_qty,
            "sets_touched": r.sets_touched,
        }
        for r in rows
    ]

    first = points[0]["value"] if points else 0
    latest = points[-1]["value"] if points else 0
    delta_usd = round(latest - first, 2)
    delta_pct = round(((latest - first) / first) * 100, 2) if first > 0 else 0.0

    return {
        "period_days": period_days,
        "points": points,
        "first_value": first,
        "latest_value": latest,
        "delta_usd": delta_usd,
        "delta_pct": delta_pct,
        "count": len(points),
    }


@router.get("/summary", response_model=dict)
async def my_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """High-level stats for the user's whole collection. Variant-aware
    pricing means user with a reverseHolofoil Larvitar gets credit for
    its $34.67 market while a normal Larvitar gets $0.50."""
    rows = (
        await db.execute(
            select(
                CollectionItem.qty,
                CollectionItem.variant,
                CollectionItem.card_id,
                Card.set_id,
                Card.tcgplayer_prices,
                Card.market_price_usd,
            )
            .join(Card, CollectionItem.card_id == Card.id)
            .where(CollectionItem.user_id == user.id)
        )
    ).all()

    unique_ids: set[str] = set()
    sets_touched: set[str] = set()
    total_entries = 0
    total_qty = 0
    value = 0.0
    for qty, variant, card_id, set_id, prices, fallback in rows:
        total_entries += 1
        unique_ids.add(card_id)
        sets_touched.add(set_id)
        total_qty += qty or 0
        p = price_for_variant(prices, variant, fallback)
        if p is not None:
            value += (qty or 0) * p

    return {
        "total_entries": total_entries,
        "unique_cards": len(unique_ids),
        "total_qty": total_qty,
        "sets_touched": len(sets_touched),
        "estimated_value_usd": round(value, 2),
    }
