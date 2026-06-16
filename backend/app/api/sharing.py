"""Portfolio sharing — opt-in public view via non-enumerable random token.

A user can:
  - Toggle public/private (default private)
  - Pick what to expose (value, growth chart, wishlist, full card grid)
  - Rotate their token at any time to invalidate an old shared URL

The public viewer endpoint `/p/{token}` is unauthenticated — anyone with
the link can see what the owner chose to expose. Tokens are 24-char URL-safe
random strings (~144 bits entropy) so guessing one is computationally
infeasible.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Card, CollectionItem, PortfolioSnapshot, Set, User, WishlistItem

router = APIRouter(tags=["sharing"])


# ────────── schemas ──────────


class SharingSettings(BaseModel):
    is_public: bool
    share_token: Optional[str]
    share_url: Optional[str]
    bio: Optional[str]
    show_value: bool
    show_growth: bool
    show_wishlist: bool
    show_all_cards: bool


class SharingUpdate(BaseModel):
    is_public: Optional[bool] = None
    bio: Optional[str] = Field(None, max_length=160)
    show_value: Optional[bool] = None
    show_growth: Optional[bool] = None
    show_wishlist: Optional[bool] = None
    show_all_cards: Optional[bool] = None


class PublicCardEntry(BaseModel):
    card_id: str
    name: str
    number: Optional[str]
    set_id: str
    set_name: str
    rarity: Optional[str]
    image_small: Optional[str]
    market_price_usd: Optional[float]
    qty: int


class PublicSetCompletion(BaseModel):
    set_id: str
    set_name: str
    owned_unique: int
    total_cards: int
    completion_pct: float


class PublicGrowthPoint(BaseModel):
    date: str
    value: float


class PublicWishlistEntry(BaseModel):
    card_id: str
    name: str
    set_name: str
    image_small: Optional[str]
    market_price_usd: Optional[float]
    max_price_usd: Optional[float]
    priority: int


class PublicPortfolio(BaseModel):
    display_name: str
    bio: Optional[str]
    # Aggregate stats — always shown when public
    unique_cards: int
    total_qty: int
    sets_touched: int
    # Value: nullable when owner chose to hide
    estimated_value_usd: Optional[float]
    # Asset mix (sum of qty × price by series) — always shown
    asset_mix: list[dict]
    # Top 20 cards by market price — always shown
    top_cards: list[PublicCardEntry]
    # Set completion bars — always shown
    set_completion: list[PublicSetCompletion]
    # Toggleable extras
    growth: Optional[list[PublicGrowthPoint]]
    wishlist: Optional[list[PublicWishlistEntry]]
    all_cards: Optional[list[PublicCardEntry]]


# ────────── helpers ──────────


def _new_share_token() -> str:
    """Generate a 24-char URL-safe random token (~144 bits entropy)."""
    return secrets.token_urlsafe(18)  # 18 bytes → ~24 char base64url


def _share_url_for(token: str | None) -> str | None:
    """Build the public URL for a token. Caller fills the actual host."""
    if not token:
        return None
    return f"/p/{token}"


# ────────── endpoints ──────────


@router.get("/me/sharing", response_model=SharingSettings)
async def get_my_sharing(
    user: User = Depends(get_current_user),
) -> SharingSettings:
    return SharingSettings(
        is_public=user.is_portfolio_public,
        share_token=user.share_token,
        share_url=_share_url_for(user.share_token),
        bio=user.portfolio_bio,
        show_value=user.portfolio_show_value,
        show_growth=user.portfolio_show_growth,
        show_wishlist=user.portfolio_show_wishlist,
        show_all_cards=user.portfolio_show_all_cards,
    )


@router.patch("/me/sharing", response_model=SharingSettings)
async def update_my_sharing(
    payload: SharingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharingSettings:
    data = payload.model_dump(exclude_unset=True)

    if "is_public" in data:
        user.is_portfolio_public = data["is_public"]
        # Generate a token the first time the user goes public so they
        # have something to share immediately.
        if user.is_portfolio_public and not user.share_token:
            user.share_token = _new_share_token()

    if "bio" in data:
        user.portfolio_bio = data["bio"]
    if "show_value" in data:
        user.portfolio_show_value = data["show_value"]
    if "show_growth" in data:
        user.portfolio_show_growth = data["show_growth"]
    if "show_wishlist" in data:
        user.portfolio_show_wishlist = data["show_wishlist"]
    if "show_all_cards" in data:
        user.portfolio_show_all_cards = data["show_all_cards"]

    await db.commit()
    await db.refresh(user)
    return await get_my_sharing(user)


@router.post("/me/sharing/rotate", response_model=SharingSettings)
async def rotate_share_token(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharingSettings:
    """Generate a new token, invalidating any previously-shared URL."""
    user.share_token = _new_share_token()
    await db.commit()
    await db.refresh(user)
    return await get_my_sharing(user)


@router.get("/p/{token}", response_model=PublicPortfolio)
async def get_public_portfolio(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicPortfolio:
    """Unauthenticated public viewer. 404 if token unknown or not public."""
    row = (
        await db.execute(select(User).where(User.share_token == token))
    ).scalar_one_or_none()
    if row is None or not row.is_portfolio_public:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # ── Aggregate stats
    stats_stmt = (
        select(
            func.count(func.distinct(CollectionItem.card_id)).label("unique_cards"),
            func.coalesce(func.sum(CollectionItem.qty), 0).label("total_qty"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Card.market_price_usd.is_not(None),
                            CollectionItem.qty * Card.market_price_usd,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("value"),
            func.count(func.distinct(Card.set_id)).label("sets_touched"),
        )
        .join(Card, CollectionItem.card_id == Card.id)
        .where(CollectionItem.user_id == row.id)
    )
    stats = (await db.execute(stats_stmt)).one()
    total_value = round(float(stats.value or 0), 2)

    # ── Asset mix by series
    mix_stmt = (
        select(
            Set.series.label("series"),
            func.sum(
                case(
                    (
                        Card.market_price_usd.is_not(None),
                        CollectionItem.qty * Card.market_price_usd,
                    ),
                    else_=0,
                )
            ).label("value"),
        )
        .join(Card, CollectionItem.card_id == Card.id)
        .join(Set, Card.set_id == Set.id)
        .where(CollectionItem.user_id == row.id)
        .group_by(Set.series)
    )
    asset_mix = [
        {"label": series or "Other", "value": round(float(v or 0), 2)}
        for series, v in (await db.execute(mix_stmt)).all()
        if (v or 0) > 0
    ]
    asset_mix.sort(key=lambda x: x["value"], reverse=True)

    # ── Top cards by market value (always shown, capped at 20)
    top_stmt = (
        select(CollectionItem, Card, Set.name)
        .join(Card, CollectionItem.card_id == Card.id)
        .join(Set, Card.set_id == Set.id)
        .where(CollectionItem.user_id == row.id)
        .where(Card.market_price_usd.is_not(None))
        .order_by(Card.market_price_usd.desc())
        .limit(20)
    )
    top_cards = [
        PublicCardEntry(
            card_id=card.id,
            name=card.name,
            number=card.number,
            set_id=card.set_id,
            set_name=set_name,
            rarity=card.rarity,
            image_small=card.image_small,
            market_price_usd=float(card.market_price_usd)
            if card.market_price_usd is not None
            else None,
            qty=item.qty,
        )
        for item, card, set_name in (await db.execute(top_stmt)).all()
    ]

    # ── Set completion bars
    sets_stmt = (
        select(
            Card.set_id,
            Set.name,
            func.count(func.distinct(Card.id)).label("total_cards"),
            func.count(
                func.distinct(
                    case((CollectionItem.user_id == row.id, Card.id), else_=None)
                )
            ).label("owned_unique"),
        )
        .select_from(Card)
        .join(Set, Card.set_id == Set.id)
        .outerjoin(
            CollectionItem,
            (CollectionItem.card_id == Card.id)
            & (CollectionItem.user_id == row.id),
        )
        .group_by(Card.set_id, Set.name)
        .having(
            func.count(
                func.distinct(
                    case((CollectionItem.user_id == row.id, Card.id), else_=None)
                )
            )
            > 0
        )
        .order_by(
            (
                func.count(
                    func.distinct(
                        case((CollectionItem.user_id == row.id, Card.id), else_=None)
                    )
                )
                * 1.0
                / func.count(func.distinct(Card.id))
            ).desc()
        )
        .limit(10)
    )
    set_completion = [
        PublicSetCompletion(
            set_id=sid,
            set_name=sname,
            owned_unique=int(owned),
            total_cards=int(total),
            completion_pct=round(float(owned) / float(total) * 100, 1)
            if total
            else 0.0,
        )
        for sid, sname, total, owned in (await db.execute(sets_stmt)).all()
    ]

    # ── Optional: growth time-series
    growth: list[PublicGrowthPoint] | None = None
    if row.portfolio_show_growth:
        growth_rows = (
            await db.execute(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.user_id == row.id)
                .order_by(PortfolioSnapshot.snapshot_date.asc())
                .limit(365)
            )
        ).scalars().all()
        growth = [
            PublicGrowthPoint(
                date=s.snapshot_date,
                value=round(float(s.estimated_value_usd), 2),
            )
            for s in growth_rows
        ]

    # ── Optional: wishlist
    wishlist: list[PublicWishlistEntry] | None = None
    if row.portfolio_show_wishlist:
        wl_stmt = (
            select(WishlistItem, Card, Set.name)
            .join(Card, WishlistItem.card_id == Card.id)
            .join(Set, Card.set_id == Set.id)
            .where(WishlistItem.user_id == row.id)
            .order_by(WishlistItem.priority.desc(), WishlistItem.created_at.desc())
        )
        wishlist = [
            PublicWishlistEntry(
                card_id=card.id,
                name=card.name,
                set_name=set_name,
                image_small=card.image_small,
                market_price_usd=float(card.market_price_usd)
                if card.market_price_usd is not None
                else None,
                max_price_usd=float(item.max_price_usd)
                if item.max_price_usd is not None
                else None,
                priority=item.priority,
            )
            for item, card, set_name in (await db.execute(wl_stmt)).all()
        ]

    # ── Optional: entire collection grid (instead of just top 20)
    all_cards: list[PublicCardEntry] | None = None
    if row.portfolio_show_all_cards:
        all_stmt = (
            select(CollectionItem, Card, Set.name)
            .join(Card, CollectionItem.card_id == Card.id)
            .join(Set, Card.set_id == Set.id)
            .where(CollectionItem.user_id == row.id)
            .order_by(
                Card.market_price_usd.desc().nullslast(),
                Card.name.asc(),
            )
        )
        all_cards = [
            PublicCardEntry(
                card_id=card.id,
                name=card.name,
                number=card.number,
                set_id=card.set_id,
                set_name=set_name,
                rarity=card.rarity,
                image_small=card.image_small,
                market_price_usd=float(card.market_price_usd)
                if card.market_price_usd is not None
                else None,
                qty=item.qty,
            )
            for item, card, set_name in (await db.execute(all_stmt)).all()
        ]

    return PublicPortfolio(
        display_name=row.name or row.email.split("@")[0],
        bio=row.portfolio_bio,
        unique_cards=int(stats.unique_cards or 0),
        total_qty=int(stats.total_qty or 0),
        sets_touched=int(stats.sets_touched or 0),
        estimated_value_usd=total_value if row.portfolio_show_value else None,
        asset_mix=asset_mix,
        top_cards=top_cards,
        set_completion=set_completion,
        growth=growth,
        wishlist=wishlist,
        all_cards=all_cards,
    )
