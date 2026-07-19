"""Sealed product ownership + wishlist routes.

Mirrors the card-side `collection.py` / `wishlist.py` endpoints but on
`sealed_collection_items` and `sealed_wishlist_items`. Kept in its own
router so the surface stays discoverable in the OpenAPI docs — a
polymorphic /items endpoint would blur the two categories.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Product,
    SealedCollectionItem,
    SealedWishlistItem,
    User,
)


router = APIRouter(prefix="/sealed", tags=["sealed"])


class SealedCollectionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: str
    qty: int
    condition: str
    purchase_price_usd: float | None
    acquisition_type: str | None
    acquired_at: str | None
    notes: str | None


class SealedCollectionItemWrite(BaseModel):
    qty: int = 1
    # sealed / opened / damaged — see model docstring. Server-side
    # pattern gate rejects anything off-list, so the frontend can't
    # send a random string and end up with a mystery bucket in the
    # portfolio.
    condition: str | None = Field(
        default=None, pattern="^(sealed|opened|damaged)$"
    )
    purchase_price_usd: float | None = None
    acquisition_type: str | None = None
    acquired_at: str | None = None  # ISO YYYY-MM-DD
    notes: str | None = None


class SealedWishlistItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: str
    target_price_usd: float | None
    notes: str | None


class SealedWishlistItemWrite(BaseModel):
    target_price_usd: float | None = None
    notes: str | None = None


# ── Collection ────────────────────────────────────────────────────


@router.get("/collection", response_model=dict)
async def list_collection(
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Every sealed product this user owns, with the joined product
    payload so the frontend can render tiles without a second call."""
    rows = (
        await db.execute(
            select(SealedCollectionItem, Product)
            .join(Product, SealedCollectionItem.product_id == Product.id)
            .where(SealedCollectionItem.user_id == user.id)
            .order_by(SealedCollectionItem.created_at.desc())
        )
    ).all()

    items = []
    total_owned = 0
    est_value = 0.0
    for row, product in rows:
        qty = row.qty or 0
        total_owned += qty
        price = product.market_price_usd or 0.0
        est_value += price * qty
        items.append(
            {
                "item": SealedCollectionItemRead.model_validate(row).model_dump(),
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "product_type": product.product_type,
                    "set_id": product.set_id,
                    "market_price_usd": product.market_price_usd,
                    "image_url": product.image_url,
                    "tcgplayer_url": product.tcgplayer_url,
                },
            }
        )

    return {
        "items": items,
        "total_owned": total_owned,
        "unique_products": len(items),
        "estimated_value_usd": round(est_value, 2),
    }


@router.get("/collection/product/{product_id}", response_model=SealedCollectionItemRead | None)
async def get_collection_entry(
    product_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SealedCollectionItemRead | None:
    """Return the user's ownership row for one product, or null if not
    owned. Used by the product detail page to decide button state."""
    row = (
        await db.execute(
            select(SealedCollectionItem)
            .where(
                SealedCollectionItem.user_id == user.id,
                SealedCollectionItem.product_id == product_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return SealedCollectionItemRead.model_validate(row) if row else None


@router.post("/collection/product/{product_id}", response_model=SealedCollectionItemRead)
async def upsert_collection_entry(
    product_id: str,
    payload: SealedCollectionItemWrite,
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SealedCollectionItemRead:
    """Mark a sealed product as owned. Overwrites any existing row for
    the same (user, product) so the frontend can call this on both
    initial add and edit."""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")

    row = (
        await db.execute(
            select(SealedCollectionItem)
            .where(
                SealedCollectionItem.user_id == user.id,
                SealedCollectionItem.product_id == product_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    parsed_acquired_at = None
    if payload.acquired_at:
        try:
            parsed_acquired_at = datetime.fromisoformat(payload.acquired_at).date()
        except ValueError:
            raise HTTPException(400, "acquired_at must be YYYY-MM-DD")

    condition = payload.condition or "sealed"
    if row is None:
        row = SealedCollectionItem(
            user_id=user.id,
            product_id=product_id,
            qty=max(1, payload.qty),
            condition=condition,
            purchase_price_usd=payload.purchase_price_usd,
            acquisition_type=payload.acquisition_type,
            acquired_at=parsed_acquired_at,
            notes=payload.notes,
        )
        db.add(row)
    else:
        row.qty = max(1, payload.qty)
        row.condition = condition
        row.purchase_price_usd = payload.purchase_price_usd
        row.acquisition_type = payload.acquisition_type
        row.acquired_at = parsed_acquired_at
        row.notes = payload.notes
    await db.commit()
    await db.refresh(row)
    return SealedCollectionItemRead.model_validate(row)


@router.delete("/collection/product/{product_id}", response_model=dict)
async def delete_collection_entry(
    product_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Un-own a sealed product. Silently no-ops if the user didn't
    own it — call sites shouldn't need to check first."""
    await db.execute(
        delete(SealedCollectionItem).where(
            SealedCollectionItem.user_id == user.id,
            SealedCollectionItem.product_id == product_id,
        )
    )
    await db.commit()
    return {"ok": True}


# ── Wishlist ──────────────────────────────────────────────────────


@router.get("/wishlist", response_model=dict)
async def list_wishlist(
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(SealedWishlistItem, Product)
            .join(Product, SealedWishlistItem.product_id == Product.id)
            .where(SealedWishlistItem.user_id == user.id)
            .order_by(SealedWishlistItem.created_at.desc())
        )
    ).all()

    items = []
    for row, product in rows:
        items.append(
            {
                "item": SealedWishlistItemRead.model_validate(row).model_dump(),
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "product_type": product.product_type,
                    "set_id": product.set_id,
                    "market_price_usd": product.market_price_usd,
                    "image_url": product.image_url,
                    "tcgplayer_url": product.tcgplayer_url,
                },
            }
        )
    return {"items": items, "count": len(items)}


@router.get("/wishlist/product/{product_id}", response_model=SealedWishlistItemRead | None)
async def get_wishlist_entry(
    product_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SealedWishlistItemRead | None:
    row = (
        await db.execute(
            select(SealedWishlistItem)
            .where(
                SealedWishlistItem.user_id == user.id,
                SealedWishlistItem.product_id == product_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return SealedWishlistItemRead.model_validate(row) if row else None


@router.post("/wishlist/product/{product_id}/toggle", response_model=dict)
async def toggle_wishlist(
    product_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add to or remove from wishlist. Returns the resulting state so
    the frontend can update its icon without a second GET."""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")

    row = (
        await db.execute(
            select(SealedWishlistItem)
            .where(
                SealedWishlistItem.user_id == user.id,
                SealedWishlistItem.product_id == product_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if row is None:
        db.add(SealedWishlistItem(user_id=user.id, product_id=product_id))
        await db.commit()
        return {"wishlisted": True}

    await db.execute(
        delete(SealedWishlistItem).where(SealedWishlistItem.id == row.id)
    )
    await db.commit()
    return {"wishlisted": False}


@router.patch("/wishlist/product/{product_id}", response_model=SealedWishlistItemRead)
async def update_wishlist_entry(
    product_id: str,
    payload: SealedWishlistItemWrite,
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> SealedWishlistItemRead:
    row = (
        await db.execute(
            select(SealedWishlistItem)
            .where(
                SealedWishlistItem.user_id == user.id,
                SealedWishlistItem.product_id == product_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Not on your wishlist")
    row.target_price_usd = payload.target_price_usd
    row.notes = payload.notes
    await db.commit()
    await db.refresh(row)
    return SealedWishlistItemRead.model_validate(row)


# ── Bulk owner/wishlist check ─────────────────────────────────────


@router.get("/state", response_model=dict)
async def user_sealed_state(
    user: Annotated[User, Depends(get_current_user)],
    product_ids: str = Query(
        "",
        description="Comma-separated product ids to check ownership + wishlist for.",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk check — returns two sets (owned_ids, wishlisted_ids) filtered
    to only the ids the frontend cares about. Lets a product list page
    render badges without fetching all-owned + all-wishlisted."""
    ids = {p.strip() for p in product_ids.split(",") if p.strip()}
    if not ids:
        return {"owned": [], "wishlisted": []}

    owned = (
        await db.execute(
            select(SealedCollectionItem.product_id)
            .where(
                SealedCollectionItem.user_id == user.id,
                SealedCollectionItem.product_id.in_(ids),
            )
        )
    ).scalars().all()
    wishlisted = (
        await db.execute(
            select(SealedWishlistItem.product_id)
            .where(
                SealedWishlistItem.user_id == user.id,
                SealedWishlistItem.product_id.in_(ids),
            )
        )
    ).scalars().all()
    return {"owned": list(owned), "wishlisted": list(wishlisted)}
