"""Extended /cards search with filters + collection-aware filters.

Public filters work without auth. Collection-aware filters (`owned`,
`condition`) silently no-op when no JWT is provided.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import Card, CollectionItem, Set, User
from app.schemas.card import CardList, CardRead

router = APIRouter(prefix="/cards", tags=["cards"])


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _json_contains(column, needles: list[str]):
    """Match SQLite JSON arrays via text containment.

    `cards.types` is stored like `["Fire", "Water"]` — a simple LIKE on the
    serialized form is the cheapest cross-portable check. Good enough for
    20k rows; we can swap for JSON1 funcs if it ever gets slow.
    """
    return or_(*[column.cast(String).like(f'%"{n}"%') for n in needles])


def _card_to_read(
    card: Card,
    set_name: str | None,
    set_printed_total: int | None,
    set_ptcgo_code: str | None,
) -> CardRead:
    data = CardRead.model_validate(card).model_dump()
    data["set_name"] = set_name
    data["set_printed_total"] = set_printed_total
    data["set_ptcgo_code"] = set_ptcgo_code
    return CardRead(**data)


SORT_OPTIONS = {
    "relevance": [Card.market_price_usd.desc().nullslast(), Card.name],
    "price_desc": [Card.market_price_usd.desc().nullslast(), Card.name],
    "price_asc": [Card.market_price_usd.asc().nullslast(), Card.name],
    "name_asc": [Card.name.asc()],
    "name_desc": [Card.name.desc()],
    "hp_desc": [Card.hp_int.desc().nullslast(), Card.name],
    "hp_asc": [Card.hp_int.asc().nullslast(), Card.name],
    "number_asc": [Card.number_int.asc().nullslast(), Card.number],
    "newest": [Set.release_date.desc().nullslast(), Card.number_int.asc().nullslast()],
}


@router.get("/filters/options")
async def filter_options(
    db: AsyncSession = Depends(get_db),
    set_id: str | None = Query(
        None,
        description=(
            "Scope card-derived options (rarities, types, subtypes, artists, "
            "hp_max, price_max) to a specific set. `sets`, `conditions`, and "
            "`sort_options` stay global."
        ),
    ),
) -> dict:
    """Return the distinct values populated for each filterable column.

    Cached client-side for the session; cheap query (<50ms).

    When `set_id` is supplied, the sidebar on a set detail page only shows
    rarities/types/etc. that *actually exist in that set* — no empty filters
    for rarities that don't apply, no Common/Uncommon for an SIR-only chase
    set.
    """
    # Scope clause re-used across every per-card query below.
    set_scope = [Card.set_id == set_id] if set_id else []

    rarities = (
        await db.execute(
            select(Card.rarity)
            .where(Card.rarity.is_not(None), *set_scope)
            .distinct()
        )
    ).scalars().all()
    supertypes = (
        await db.execute(
            select(Card.supertype)
            .where(Card.supertype.is_not(None), *set_scope)
            .distinct()
        )
    ).scalars().all()

    types_rows = (
        await db.execute(
            select(Card.types).where(Card.types.is_not(None), *set_scope)
        )
    ).scalars().all()
    types_flat: set[str] = set()
    for arr in types_rows:
        if isinstance(arr, list):
            types_flat.update(arr)

    subtypes_rows = (
        await db.execute(
            select(Card.subtypes).where(Card.subtypes.is_not(None), *set_scope)
        )
    ).scalars().all()
    subtypes_flat: set[str] = set()
    for arr in subtypes_rows:
        if isinstance(arr, list):
            subtypes_flat.update(arr)

    hp_max = (
        await db.execute(select(func.max(Card.hp_int)).where(*set_scope))
    ).scalar_one() or 0
    price_max = (
        await db.execute(
            select(func.max(Card.market_price_usd)).where(*set_scope)
        )
    ).scalar_one() or 0

    sets = (
        await db.execute(
            select(Set.id, Set.name, Set.series, Set.release_date)
            .order_by(Set.release_date.desc().nullslast())
        )
    ).all()

    # Artists with usage counts so we can sort by popularity, fall back to name.
    artist_rows = (
        await db.execute(
            select(Card.artist, func.count(Card.id).label("count"))
            .where(Card.artist.is_not(None), *set_scope)
            .group_by(Card.artist)
        )
    ).all()
    artists = sorted(
        [{"name": a, "count": c} for a, c in artist_rows if a],
        key=lambda r: (-r["count"], r["name"].lower()),
    )

    return {
        "rarities": sorted([r for r in rarities if r]),
        "supertypes": sorted([s for s in supertypes if s]),
        "types": sorted(types_flat),
        "subtypes": sorted(subtypes_flat),
        "hp_max": hp_max,
        "price_max": round(float(price_max), 2),
        "sets": [
            {
                "id": sid,
                "name": name,
                "series": series,
                "release_date": rd.isoformat() if rd else None,
            }
            for sid, name, series, rd in sets
        ],
        "artists": artists,
        "conditions": ["NM", "LP", "MP", "HP", "DMG"],
        "sort_options": list(SORT_OPTIONS.keys()),
    }


@router.get("/browse", response_model=CardList)
async def browse_cards(
    db: AsyncSession = Depends(get_db),
    user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    q: str | None = Query(None, description="Card name substring"),
    set_id: str | None = Query(None, description="Comma-separated set ids"),
    rarity: str | None = Query(None),
    supertype: str | None = Query(None),
    type: str | None = Query(None, description="Energy type (Fire, Water, ...)"),
    subtype: str | None = Query(None, description="Stage/Ability/etc."),
    hp_min: int | None = Query(None, ge=0),
    hp_max: int | None = Query(None, ge=0),
    price_min: float | None = Query(None, ge=0),
    price_max: float | None = Query(None, ge=0),
    artist: str | None = Query(None, description="Substring match"),
    owned: str | None = Query(None, description="all / in / not_in"),
    condition: str | None = Query(None, description="Comma-separated NM,LP,..."),
    sort: str = Query("relevance"),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=250),
) -> CardList:
    if sort not in SORT_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown sort '{sort}'")

    base_stmt = select(Card, Set.name, Set.printed_total, Set.ptcgo_code).join(
        Set, Card.set_id == Set.id
    )

    filters = []

    if q:
        filters.append(Card.name.ilike(f"%{q}%"))

    set_ids = _split_csv(set_id)
    if set_ids:
        filters.append(Card.set_id.in_(set_ids))

    rarities = _split_csv(rarity)
    if rarities:
        filters.append(Card.rarity.in_(rarities))

    supertypes = _split_csv(supertype)
    if supertypes:
        filters.append(Card.supertype.in_(supertypes))

    types = _split_csv(type)
    if types:
        filters.append(_json_contains(Card.types, types))

    subtypes = _split_csv(subtype)
    if subtypes:
        filters.append(_json_contains(Card.subtypes, subtypes))

    if hp_min is not None:
        filters.append(Card.hp_int >= hp_min)
    if hp_max is not None:
        filters.append(Card.hp_int <= hp_max)

    if price_min is not None:
        filters.append(Card.market_price_usd >= price_min)
    if price_max is not None:
        filters.append(Card.market_price_usd <= price_max)

    artists_sel = _split_csv(artist)
    if artists_sel:
        filters.append(Card.artist.in_(artists_sel))

    # Collection-aware filters — only when authenticated.
    if user and owned in ("in", "not_in"):
        owned_subq = (
            select(CollectionItem.card_id)
            .where(CollectionItem.user_id == user.id)
            .distinct()
            .scalar_subquery()
        )
        if owned == "in":
            filters.append(Card.id.in_(owned_subq))
        else:
            filters.append(Card.id.not_in(owned_subq))

    if user and condition:
        conds = _split_csv(condition)
        if conds:
            cond_subq = (
                select(CollectionItem.card_id)
                .where(
                    CollectionItem.user_id == user.id,
                    CollectionItem.condition.in_(conds),
                )
                .distinct()
                .scalar_subquery()
            )
            filters.append(Card.id.in_(cond_subq))

    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    # Total count for pagination.
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Order + page.
    stmt = base_stmt.order_by(*SORT_OPTIONS[sort])
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
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
