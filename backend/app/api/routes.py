from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import Card, CardPriceSnapshot, CollectionItem, Set, User
from app.schemas.card import CardList, CardRead
from app.schemas.set import SetRead, SetWithCardCount
from app.services.ebay_client import POKEMON_CATEGORIES, EbayClient, EbayClientError, build_card_query

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/sets", response_model=list[SetWithCardCount])
async def list_sets(
    db: AsyncSession = Depends(get_db),
    series: str | None = Query(None, description="Filter by series name"),
    current_user: User | None = Depends(get_current_user_optional),
) -> list[SetWithCardCount]:
    stmt = (
        select(
            Set,
            func.count(Card.id).label("card_count"),
            func.sum(Card.market_price_usd).label("total_value"),
        )
        .outerjoin(Card, Card.set_id == Set.id)
        .group_by(Set.id)
        .order_by(Set.release_date.desc().nullslast())
    )
    if series:
        stmt = stmt.where(Set.series == series)

    rows = (await db.execute(stmt)).all()

    # Per-user owned counts in one query if logged in
    owned_map: dict[str, int] = {}
    if current_user is not None:
        owned_stmt = (
            select(
                Card.set_id,
                func.count(distinct(CollectionItem.card_id)).label("owned"),
            )
            .join(CollectionItem, CollectionItem.card_id == Card.id)
            .where(CollectionItem.user_id == current_user.id)
            .group_by(Card.set_id)
        )
        for set_id, owned in (await db.execute(owned_stmt)).all():
            owned_map[set_id] = int(owned)

    return [
        SetWithCardCount(
            **SetRead.model_validate(set_row).model_dump(),
            card_count=count,
            total_value_usd=float(total_value) if total_value is not None else None,
            owned_unique=owned_map.get(set_row.id) if current_user else None,
        )
        for set_row, count, total_value in rows
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


@router.get("/cards/{card_id}/neighbors")
async def get_neighbors(
    card_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Previous/next card in the same set by sort order (number_int, number)."""
    base = await db.get(Card, card_id)
    if not base:
        raise HTTPException(status_code=404, detail="Card not found")

    stmt = (
        select(Card.id, Card.name, Card.number, Card.image_small)
        .where(Card.set_id == base.set_id)
        .order_by(
            Card.number_int.is_(None),
            Card.number_int,
            Card.number,
        )
    )
    rows = (await db.execute(stmt)).all()

    idx = next((i for i, r in enumerate(rows) if r.id == card_id), None)
    if idx is None:
        return {"prev": None, "next": None, "position": None, "total": len(rows)}

    def serialize(r) -> dict:
        return {
            "id": r.id,
            "name": r.name,
            "number": r.number,
            "image_small": r.image_small,
        }

    return {
        "prev": serialize(rows[idx - 1]) if idx > 0 else None,
        "next": serialize(rows[idx + 1]) if idx < len(rows) - 1 else None,
        "position": idx + 1,
        "total": len(rows),
    }


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


@router.get("/cards/trending")
async def get_trending(
    db: AsyncSession = Depends(get_db),
    period_days: int = Query(7, ge=1, le=90),
    source: str = Query("ebay", description="Snapshot source: ebay / tcgplayer / cardmarket"),
    direction: str = Query("up", description="up = top gainers, down = top losers"),
    limit: int = Query(20, ge=1, le=50),
    min_price_usd: float = Query(
        1.0,
        ge=0,
        description=(
            "Price floor (both endpoints). Filters out penny-stock artifacts — "
            "a $0.02 → $0.27 card is a +1250% mover by math, but useless signal."
        ),
    ),
    min_abs_change_usd: float = Query(
        0.5,
        ge=0,
        description="Minimum absolute $ change between oldest and latest snapshot.",
    ),
) -> dict:
    """Top movers — cards with the biggest %change over the last `period_days`.

    Needs at least 2 snapshots per card in the window. With a fresh daily cron
    expect this to be sparse for the first few days, then fill in.

    Cards under `min_price_usd` (default $1) or with absolute change below
    `min_abs_change_usd` (default $0.50) are excluded so the list surfaces
    movements that actually matter to collectors.
    """
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")

    cutoff = (date.today() - timedelta(days=period_days)).isoformat()

    snap_stmt = (
        select(CardPriceSnapshot)
        .where(CardPriceSnapshot.source == source)
        .where(CardPriceSnapshot.snapshot_date >= cutoff)
        .order_by(CardPriceSnapshot.card_id, CardPriceSnapshot.snapshot_date)
    )
    snapshots = list((await db.execute(snap_stmt)).scalars())

    # Group by (card_id, variant) — comparing different variants of the same
    # card is meaningless (a card's "normal" $0.02 vs "holofoil" $0.27 is not
    # a price movement, it's two products). Per card we then pick the variant
    # with the largest absolute %change to surface as that card's mover.
    by_card_variant: dict[tuple[str, str], list[CardPriceSnapshot]] = {}
    for s in snapshots:
        by_card_variant.setdefault((s.card_id, s.variant), []).append(s)

    best_per_card: dict[str, dict] = {}
    for (card_id, variant), snaps in by_card_variant.items():
        if len(snaps) < 2:
            continue
        snaps.sort(key=lambda s: s.snapshot_date)
        oldest = snaps[0].market_price_usd
        latest = snaps[-1].market_price_usd
        if oldest is None or latest is None or oldest <= 0:
            continue
        # Quality floors — both endpoints must clear the price floor AND the
        # absolute change must be meaningful.
        if float(oldest) < min_price_usd or float(latest) < min_price_usd:
            continue
        if abs(float(latest) - float(oldest)) < min_abs_change_usd:
            continue
        delta_pct = ((latest - oldest) / oldest) * 100.0
        entry = {
            "card_id": card_id,
            "variant": variant,
            "latest_price": float(latest),
            "oldest_price": float(oldest),
            "delta_pct": delta_pct,
            "snapshots_count": len(snaps),
        }
        # Keep the variant with the largest absolute %change per card.
        prior = best_per_card.get(card_id)
        if prior is None or abs(delta_pct) > abs(prior["delta_pct"]):
            best_per_card[card_id] = entry

    movers: list[dict] = list(best_per_card.values())

    movers.sort(key=lambda x: x["delta_pct"], reverse=(direction == "up"))
    top = movers[:limit]

    if top:
        card_ids = [m["card_id"] for m in top]
        cards_stmt = (
            select(Card, Set.name)
            .join(Set, Card.set_id == Set.id)
            .where(Card.id.in_(card_ids))
        )
        cards_map = {}
        for c, set_name in (await db.execute(cards_stmt)).all():
            cards_map[c.id] = (c, set_name)
        for m in top:
            entry = cards_map.get(m["card_id"])
            if entry:
                c, set_name = entry
                m["name"] = c.name
                m["number"] = c.number
                m["set_id"] = c.set_id
                m["set_name"] = set_name
                m["image_small"] = c.image_small
                m["rarity"] = c.rarity

    return {
        "period_days": period_days,
        "source": source,
        "direction": direction,
        "movers": top,
        "total_eligible": len(movers),
    }


@router.get("/cards/{card_id}/live-listings")
async def get_live_listings(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=20),
) -> dict:
    """Hit eBay Browse API in real-time and return the top live listings for this card.

    Uses the same noise-filtered query as the snapshot script. One call per request.
    Frontend should cache (the standard apiFetch helper caches for 5 min).
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    set_obj = await db.get(Set, card.set_id) if card.set_id else None
    query = build_card_query(
        card_name=card.name,
        card_number=card.number,
        printed_total=set_obj.printed_total if set_obj else None,
        set_name=set_obj.name if set_obj else None,
    )

    try:
        async with EbayClient() as ebay:
            result = await ebay.browse_search(
                query,
                limit=limit,
                category_id=POKEMON_CATEGORIES["tcg_root"],
            )
    except EbayClientError as e:
        return {"listings": [], "query": query, "error": str(e)}
    except Exception as e:
        return {"listings": [], "query": query, "error": f"unexpected: {e}"}

    listings = []
    for it in result.get("itemSummaries") or []:
        try:
            price_obj = it.get("price") or {}
            price_v = float(price_obj.get("value", 0))
            currency = price_obj.get("currency", "USD")
            if currency != "USD" or price_v <= 0:
                continue
            ship_cost = 0.0
            ship_opts = it.get("shippingOptions") or []
            if ship_opts:
                ship_obj = ship_opts[0].get("shippingCost") or {}
                try:
                    ship_cost = float(ship_obj.get("value", 0))
                except (TypeError, ValueError):
                    ship_cost = 0.0
            seller = it.get("seller") or {}
            listings.append({
                "title": (it.get("title") or "")[:180],
                "price_usd": price_v,
                "shipping_usd": ship_cost,
                "total_usd": price_v + ship_cost,
                "condition": it.get("condition") or "Ungraded",
                "seller": seller.get("username") or "?",
                "seller_feedback_pct": seller.get("feedbackPercentage"),
                "url": it.get("itemWebUrl") or "",
                "source": "eBay",
            })
        except Exception:
            continue

    listings.sort(key=lambda x: x["total_usd"])
    return {"listings": listings, "query": query, "count": len(listings)}


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
