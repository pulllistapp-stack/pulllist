import asyncio
import re
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import Card, CardPriceSnapshot, CollectionItem, NewsView, Product, Set, User
from app.schemas.card import CardList, CardRead
from app.schemas.set import SetRead, SetWithCardCount
from app.services.ebay_client import POKEMON_CATEGORIES, EbayClient, EbayClientError, build_card_query
from app.services.listing_match import (
    filter_listings,
    is_low_outlier_price,
    is_suspicious,
    seller_trust_tier,
)

router = APIRouter()


# Trending rarity buckets. The boundary is Double Rare — a Common can move
# +50% on a hype cycle and a SIR can move +50% on a single grading bump, but
# collectors look for those two things in entirely different ways. Splitting
# the trending feeds lets each audience see what they care about.
#
# JP rarity codes (C, U, R, RR, etc.) live alongside the English names so a
# single set of strings filters both catalogs.
RARITY_BULK = {
    "Common", "Uncommon", "Rare", "Rare Holo", "Double Rare",
    # JP
    "C", "U", "R", "RR",
}
RARITY_CHASE = {
    # Modern EN
    "Ultra Rare", "Hyper Rare", "Illustration Rare",
    "Special Illustration Rare", "Rare Secret", "Rare Rainbow",
    "Radiant Rare", "Amazing Rare", "Rare Shiny", "Rare Shiny GX",
    "ACE SPEC Rare", "Rare BREAK", "Rare Prism Star", "Rare Holo Star",
    "Rare Holo EX", "Rare Holo GX", "Rare Holo V", "Rare Holo VMAX",
    "Rare Holo VSTAR", "Rare Holo LV.X", "Rare Shining", "Rare Prime",
    "Rare Promo", "Promo", "Legend", "Classic Collection",
    "Trainer Gallery Rare Holo", "Rare Ace",
    # JP
    "RRR", "AR", "SR", "SAR", "UR", "HR", "CSR", "CHR",
    "MR", "MUR", "SSR",
}


def _median(values: list[float | None]) -> float | None:
    """Median of non-null prices; returns None if the list is all-null/empty."""
    clean = sorted(float(v) for v in values if v is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def _mad_ratio(prices: list[float]) -> float:
    """Median absolute deviation / median. High value means the price series
    has a wide spread relative to its center — likely a noisy/spiky card."""
    if len(prices) < 2:
        return 0.0
    med = _median(prices)
    if med is None or med <= 0:
        return float("inf")
    devs = sorted(abs(p - med) for p in prices)
    mid = len(devs) // 2
    mad = devs[mid] if len(devs) % 2 else (devs[mid - 1] + devs[mid]) / 2.0
    return mad / med


def _has_lone_spike(prices: list[float], ratio: float = 2.5) -> bool:
    """True if the max price is `ratio`x bigger than the median of the rest.
    Catches single-sale outliers that poison a tercile mean — a $30 flat
    series with one $238 entry trips this immediately."""
    if len(prices) < 3:
        return False
    sorted_p = sorted(prices)
    rest = sorted_p[:-1]
    rest_med = _median(rest)
    if rest_med is None or rest_med <= 0:
        return False
    return sorted_p[-1] / rest_med >= ratio


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/sets", response_model=list[SetWithCardCount])
async def list_sets(
    db: AsyncSession = Depends(get_db),
    series: str | None = Query(None, description="Filter by series name"),
    language: str = Query(
        "en",
        description="Catalog language: 'en' (default, pokemontcg.io English), 'ja' (TCGdex Japanese). 'ko' is reserved; no data yet.",
        pattern="^(en|ja|ko)$",
    ),
    current_user: User | None = Depends(get_current_user_optional),
) -> list[SetWithCardCount]:
    stmt = (
        select(
            Set,
            func.count(Card.id).label("card_count"),
            func.sum(Card.market_price_usd).label("total_value"),
            func.sum(Card.mid_price_usd).label("total_mid"),
            func.sum(Card.low_price_usd).label("total_low"),
            func.sum(Card.high_price_usd).label("total_high"),
        )
        .outerjoin(Card, Card.set_id == Set.id)
        .where(Set.language == language)
        .group_by(Set.id)
        .order_by(Set.release_date.desc().nullslast())
    )
    if series:
        stmt = stmt.where(Set.series == series)

    rows = (await db.execute(stmt)).all()

    # JP visibility rule: show a set when it carries either a logo,
    # at least one card, or at least one sealed product. The old rule
    # was logo-or-cards; sealed-only sets (SBC / JPP-M / CLL / NPF1 /
    # PtA-GF / PtA-LP — created 2026-07-14 for the JP-sealed backfill)
    # got hidden even though their /sets/{id} page carried real
    # product tiles, so nobody could discover them by browsing.
    #
    # The carve-out: TCGdex returns stub rows for prehistoric promo
    # buckets (JPP-MCD / JPP-SI / JPP-VM / etc.) and a few never-
    # populated expansion shells (ADV1-5, L1a, LL) — no source has
    # ever filled them with cards OR sealed, so surfacing them still
    # creates empty tiles. Hide the no-logo-AND-no-cards-AND-no-sealed
    # intersection only.
    if language == "ja":
        sealed_set_ids: set[str] = set(
            (await db.execute(
                select(Product.set_id).where(Product.set_id.is_not(None)).distinct()
            )).scalars().all()
        )
        rows = [
            r for r in rows
            if r[0].logo_url is not None
            or r[1] > 0
            or r[0].id in sealed_set_ids
        ]

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
            total_value_mid_usd=float(total_mid) if total_mid is not None else None,
            total_value_low_usd=float(total_low) if total_low is not None else None,
            total_value_high_usd=float(total_high) if total_high is not None else None,
            owned_unique=owned_map.get(set_row.id) if current_user else None,
        )
        for set_row, count, total_value, total_mid, total_low, total_high in rows
    ]


@router.get("/sets/{set_id}", response_model=SetWithCardCount)
async def get_set(
    set_id: str, db: AsyncSession = Depends(get_db)
) -> SetWithCardCount:
    stmt = (
        select(
            Set,
            func.count(Card.id).label("card_count"),
            func.sum(Card.market_price_usd).label("total_value"),
            func.sum(Card.mid_price_usd).label("total_mid"),
            func.sum(Card.low_price_usd).label("total_low"),
            func.sum(Card.high_price_usd).label("total_high"),
        )
        .outerjoin(Card, Card.set_id == Set.id)
        .where(Set.id == set_id)
        .group_by(Set.id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Set not found")
    set_row, count, total_value, total_mid, total_low, total_high = row
    return SetWithCardCount(
        **SetRead.model_validate(set_row).model_dump(),
        card_count=count,
        total_value_usd=float(total_value) if total_value is not None else None,
        total_value_mid_usd=float(total_mid) if total_mid is not None else None,
        total_value_low_usd=float(total_low) if total_low is not None else None,
        total_value_high_usd=float(total_high) if total_high is not None else None,
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
    sort: str = Query(
        "number",
        pattern="^(number|price_desc|price_asc)$",
        description=(
            "number (default) = the printed collector order. "
            "price_desc / price_asc = sort by market_price_usd for the "
            "'top cards in this set' feed used by the set-overview newsbot."
        ),
    ),
) -> CardList:
    offset = (page - 1) * page_size

    set_row = await db.get(Set, set_id)
    if not set_row:
        raise HTTPException(status_code=404, detail="Set not found")

    total_stmt = select(func.count(Card.id)).where(Card.set_id == set_id)
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = select(Card).where(Card.set_id == set_id)
    if sort == "price_desc":
        stmt = stmt.order_by(Card.market_price_usd.desc().nullslast(), Card.name)
    elif sort == "price_asc":
        stmt = stmt.order_by(Card.market_price_usd.asc().nullsfirst(), Card.name)
    else:
        stmt = stmt.order_by(
            Card.number_int.is_(None),
            Card.number_int,
            Card.number,
        )
    stmt = stmt.offset(offset).limit(page_size)
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


async def _expand_query_to_dex_numbers(
    db: AsyncSession, pattern: str
) -> list[int]:
    """Look up Pokédex numbers for any card name matching `pattern`, across
    all languages. This is how cross-language search works: a user types
    "Charizard" → we find dex #6 from the EN cards → the second query
    pulls every JP/KR card that shares that dex id, even though their
    own `name` column is "リザードン" or "리자몽".

    Done in Python rather than SQL: the result set is bounded by the
    name match (rarely more than a few hundred cards) so the extra row
    transfer is cheap, and we avoid JSONB casting edge cases that bite
    when a card's national_pokedex_numbers happens to contain non-int
    entries from a flaky import.
    """
    stmt = select(Card.national_pokedex_numbers).where(
        Card.name.ilike(pattern),
        Card.national_pokedex_numbers.isnot(None),
    )
    rows = (await db.execute(stmt)).all()
    dex_set: set[int] = set()
    for (dex_list,) in rows:
        # Only expand from single-Pokémon cards. Tag-team cards like
        # "Reshiram & Charizard-GX" have dex_numbers = [6, 643] — if we
        # add 643 to the expansion set, a "Charizard" search drags every
        # solo Reshiram card into the results. Skipping multi-entry lists
        # eliminates that contamination at the cost of not cross-language-
        # matching pure tag-team names (rare case, handled by direct name
        # match for tag teams that share English nomenclature).
        if not dex_list or len(dex_list) != 1:
            continue
        try:
            dex_set.add(int(dex_list[0]))
        except (TypeError, ValueError):
            continue
    return sorted(dex_set)


def _cards_match_predicate(pattern: str, dex_numbers: list[int]):
    """OR-predicate: card name matches OR its pokédex array contains any dex
    in `dex_numbers`. Returns a single SQLAlchemy whereclause.

    Uses JSONB containment (@>) rather than ?| because SQLAlchemy's text()
    treats `?` as a positional bind placeholder and chokes on JSONB key-
    exists operators. Dex numbers come from our own query (never user
    input) so int-coercing them into the SQL string is safe from injection.
    """
    if not dex_numbers:
        return Card.name.ilike(pattern)
    dex_sql = " OR ".join(
        f"(national_pokedex_numbers::jsonb @> '[{int(n)}]'::jsonb)"
        for n in dex_numbers
    )
    return or_(
        Card.name.ilike(pattern),
        text(f"({dex_sql})"),
    )


@router.get("/cards/top-ebay-sales")
async def top_ebay_sales(
    db: AsyncSession = Depends(get_db),
    days: int = Query(
        7, ge=1, le=90,
        description="Window for the sales-count aggregation.",
    ),
    min_price_usd: float = Query(
        50.0, ge=0,
        description=(
            "Only count cards priced at or above this floor. Filters out "
            "the eBay bulk churn (Common/Uncommon flip lots that trade "
            "hundreds of times a week at $3) so the ranking surfaces "
            "actual collectible-tier activity."
        ),
    ),
    limit: int = Query(15, ge=1, le=50),
    language: str = Query("en", pattern="^(en|ja|ko)$"),
) -> dict:
    """Weekly eBay auction highlights — cards with the highest sold
    activity in the window.

    Sums sales_count across every eBay snapshot for each card in the
    window (Mon+Thu cadence means 1-3 snapshots per card typically),
    joins with the latest known market_price_usd for context, orders
    by total sales_count. Newsbot Sprint 5 uses this for the weekly
    'what actually traded' post.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    stmt = (
        select(
            CardPriceSnapshot.card_id,
            func.sum(CardPriceSnapshot.sales_count).label("total_sales"),
            func.max(CardPriceSnapshot.market_price_usd).label("recent_price"),
        )
        .where(
            CardPriceSnapshot.source == "ebay",
            CardPriceSnapshot.snapshot_date >= cutoff,
            CardPriceSnapshot.sales_count.is_not(None),
            CardPriceSnapshot.market_price_usd.is_not(None),
            CardPriceSnapshot.market_price_usd >= min_price_usd,
        )
        .group_by(CardPriceSnapshot.card_id)
        .order_by(func.sum(CardPriceSnapshot.sales_count).desc())
        .limit(limit * 3)  # over-fetch — some rows may drop out on the
                           # card-language filter below.
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return {
            "days": days,
            "min_price_usd": min_price_usd,
            "limit": limit,
            "language": language,
            "count": 0,
            "items": [],
        }

    card_ids = [r[0] for r in rows]
    card_rows = (
        await db.execute(
            select(Card, Set.name, Set.release_date, Set.logo_url)
            .join(Set, Card.set_id == Set.id)
            .where(Card.id.in_(card_ids), Card.language == language)
        )
    ).all()
    card_map = {c.id: (c, set_name, set_release, set_logo)
                for c, set_name, set_release, set_logo in card_rows}

    items = []
    for card_id, total_sales, recent_price in rows:
        entry = card_map.get(card_id)
        if not entry:
            continue  # snapshot exists but card row was filtered out by language
        c, set_name, set_release, set_logo = entry
        items.append({
            "card_id": c.id,
            "name": c.name,
            "number": c.number,
            "rarity": c.rarity,
            "artist": c.artist,
            "image_small": c.image_small,
            "image_large": c.image_large,
            "total_sales_count": int(total_sales) if total_sales else 0,
            "recent_price_usd": (
                float(recent_price) if recent_price is not None else None
            ),
            "set_id": c.set_id,
            "set_name": set_name,
            "set_release_date": (
                set_release.isoformat() if set_release else None
            ),
            "set_logo_url": set_logo,
        })
        if len(items) >= limit:
            break

    return {
        "days": days,
        "min_price_usd": min_price_usd,
        "limit": limit,
        "language": language,
        "count": len(items),
        "items": items,
    }


@router.get("/cards/top-artists")
async def top_artists(
    db: AsyncSession = Depends(get_db),
    min_usd: float = Query(
        100.0, ge=0,
        description=(
            "Only count cards priced at or above this floor. Lower values "
            "count bulk illustrations toward the ranking; the default $100 "
            "restricts to hunt-worthy cards, which is what the illustrator "
            "feature newsbot cares about."
        ),
    ),
    limit: int = Query(10, ge=1, le=50),
    language: str = Query("en", pattern="^(en|ja|ko)$"),
) -> dict:
    """Top illustrators by count of qualifying cards.

    Data-driven newsbot uses this to auto-rotate the monthly
    illustrator feature — it fetches the top artist, then feeds that
    name to /cards/by-artist for the actual gallery. Ignoring artists
    with fewer than 3 chase cards keeps the ranking away from one-hit
    contributors.
    """
    stmt = (
        select(
            Card.artist,
            func.count(Card.id).label("card_count"),
            func.max(Card.market_price_usd).label("top_price"),
        )
        .where(
            Card.language == language,
            Card.artist.is_not(None),
            Card.market_price_usd.is_not(None),
            Card.market_price_usd >= min_usd,
        )
        .group_by(Card.artist)
        .having(func.count(Card.id) >= 3)
        .order_by(func.count(Card.id).desc(), func.max(Card.market_price_usd).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "min_usd": min_usd,
        "limit": limit,
        "language": language,
        "artists": [
            {
                "artist": artist,
                "card_count": int(count),
                "top_price_usd": float(top) if top is not None else None,
            }
            for artist, count, top in rows
        ],
    }


@router.get("/cards/by-artist")
async def cards_by_artist(
    db: AsyncSession = Depends(get_db),
    artist: str = Query(..., min_length=1, description="Exact artist credit as stored on Card.artist"),
    limit: int = Query(15, ge=1, le=50),
    language: str = Query("en", pattern="^(en|ja|ko)$"),
    sort: str = Query("price_desc", pattern="^(price_desc|newest|oldest)$"),
) -> dict:
    """Top cards credited to a specific artist.

    Newsbot's illustrator-feature source calls this once per pick to
    fill the gallery + rank/set metadata for the post. Not paginated
    on purpose — the feature is a bounded gallery, not a browse feed.
    """
    stmt = (
        select(Card, Set.name, Set.release_date, Set.logo_url)
        .join(Set, Card.set_id == Set.id)
        .where(
            Card.language == language,
            Card.artist == artist,
        )
    )
    if sort == "price_desc":
        stmt = stmt.order_by(Card.market_price_usd.desc().nullslast(), Card.name)
    elif sort == "newest":
        stmt = stmt.order_by(Set.release_date.desc().nullslast(), Card.name)
    else:
        stmt = stmt.order_by(Set.release_date.asc().nullslast(), Card.name)
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).all()
    return {
        "artist": artist,
        "language": language,
        "sort": sort,
        "limit": limit,
        "count": len(rows),
        "items": [
            {
                "card_id": c.id,
                "name": c.name,
                "number": c.number,
                "rarity": c.rarity,
                "image_small": c.image_small,
                "image_large": c.image_large,
                "market_price_usd": (
                    float(c.market_price_usd) if c.market_price_usd else None
                ),
                "set_id": c.set_id,
                "set_name": set_name,
                "set_release_date": (
                    set_release.isoformat() if set_release else None
                ),
                "set_logo_url": set_logo,
            }
            for c, set_name, set_release, set_logo in rows
        ],
    }


@router.get("/cards/top-priced")
async def top_priced_cards(
    db: AsyncSession = Depends(get_db),
    min_usd: float = Query(
        1000.0, ge=0,
        description=(
            "Lower price bound. Default matches the newsbot's monthly "
            "'$1000+ club' ranking; set to 500 or 100 for smaller-scope "
            "rankings."
        ),
    ),
    limit: int = Query(20, ge=1, le=100),
    language: str = Query("en", pattern="^(en|ja|ko)$"),
) -> dict:
    """Straight top-N cards by market_price_usd, filtered to a floor.

    Data-driven newsbot uses this for the monthly '$1000 club' post
    (Collectory-style ranking). Not paginated on purpose — the list
    is meant to be a curated ranking, not a browse feed.

    Returned rows carry everything the newsbot generator prompt
    needs: card_id, name, image, rarity, artist, market price,
    set name + release date + logo (so the post can attribute each
    card to its set with a link).
    """
    stmt = (
        select(Card, Set.name, Set.release_date, Set.logo_url)
        .join(Set, Card.set_id == Set.id)
        .where(
            Card.language == language,
            Card.market_price_usd.is_not(None),
            Card.market_price_usd >= min_usd,
        )
        .order_by(Card.market_price_usd.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    items = [
        {
            "card_id": c.id,
            "name": c.name,
            "number": c.number,
            "rarity": c.rarity,
            "artist": c.artist,
            "image_small": c.image_small,
            "image_large": c.image_large,
            "market_price_usd": float(c.market_price_usd) if c.market_price_usd else None,
            "set_id": c.set_id,
            "set_name": set_name,
            "set_release_date": (
                set_release.isoformat() if set_release else None
            ),
            "set_logo_url": set_logo,
        }
        for c, set_name, set_release, set_logo in rows
    ]
    return {
        "min_usd": min_usd,
        "limit": limit,
        "language": language,
        "count": len(items),
        "items": items,
    }


@router.get("/cards/search", response_model=CardList)
async def search_cards(
    q: str = Query(..., min_length=1, description="Search query"),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    language: str | None = Query(
        None,
        description=(
            "Filter to one catalog language (en/ja/ko). Omit to search "
            "across all languages — cross-language matches use Pokédex "
            "number expansion so e.g. 'Charizard' surfaces リザードン too."
        ),
        pattern="^(en|ja|ko)$",
    ),
    cross_language: bool = Query(
        True,
        description=(
            "When true, expand the name match to other-language cards "
            "sharing a National Pokédex number (Pokémon cards only)."
        ),
    ),
    sort: str = Query(
        "relevance",
        pattern="^(relevance|price_desc|price_asc|newest|oldest)$",
        description=(
            "relevance (default) keeps exact-name matches first then highest "
            "priced. price_desc / price_asc are pure market-price sorts. "
            "newest / oldest order by the set's release_date."
        ),
    ),
) -> CardList:
    offset = (page - 1) * page_size
    pattern = f"%{q}%"

    dex_numbers: list[int] = []
    if cross_language:
        dex_numbers = await _expand_query_to_dex_numbers(db, pattern)
    where = _cards_match_predicate(pattern, dex_numbers)

    base_q = select(Card).where(where)
    if language is not None:
        base_q = base_q.where(Card.language == language)

    total_stmt = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(Card, Set.name, Set.printed_total, Set.ptcgo_code)
        .join(Set, Card.set_id == Set.id)
        .where(where)
    )
    if language is not None:
        stmt = stmt.where(Card.language == language)

    if sort == "price_desc":
        order_by = (Card.market_price_usd.desc().nullslast(), Card.name)
    elif sort == "price_asc":
        order_by = (Card.market_price_usd.asc().nullsfirst(), Card.name)
    elif sort == "newest":
        order_by = (Set.release_date.desc().nullslast(), Card.name)
    elif sort == "oldest":
        order_by = (Set.release_date.asc().nullslast(), Card.name)
    else:
        # relevance: prefer exact name hits over dex-only cross-language matches
        # so a user searching "Charizard" still sees the EN cards first; JP cards
        # with the same dex number follow.
        order_by = (
            Card.name.ilike(pattern).desc(),
            Card.market_price_usd.desc().nullslast(),
            Card.name,
        )

    stmt = stmt.order_by(*order_by).offset(offset).limit(page_size)
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
    cross_language: bool = Query(
        True,
        description="Expand suggestions to other-language cards via Pokédex number.",
    ),
) -> list[dict]:
    pattern = f"{q}%"
    pattern_contains = f"%{q}%"

    dex_numbers: list[int] = []
    if cross_language:
        dex_numbers = await _expand_query_to_dex_numbers(db, pattern_contains)
    where = _cards_match_predicate(pattern_contains, dex_numbers)

    stmt = (
        select(Card, Set.name)
        .join(Set, Card.set_id == Set.id)
        .where(where)
        .order_by(
            Card.name.ilike(pattern).desc(),
            Card.name.ilike(pattern_contains).desc(),
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


# Base Pokémon name extraction for the empty-search suggestion list.
# A single physical Pokémon often appears across dozens of cards under
# different SKU names: "Charizard", "Charizard ex", "Mega Charizard EX",
# "Dark Charizard", "Shining Charizard". Stripping the variant
# prefixes + suffixes lets us group them under one chip so clicking
# "Charizard" runs a plain text search that surfaces them all.
#
# Order in _SUFFIX_RE matters: VMAX must match before V so "Charizard
# VMAX" doesn't get reduced to "Charizard MAX".
_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")
_SUFFIX_RE = re.compile(
    r"\s+(?:VMAX|VSTAR|V-UNION|BREAK|LV\.X|Prime|ex|EX|GX|V|☆|\*|δ)$"
)
_PREFIX_RE = re.compile(
    r"^(?:Mega\s|M-|Dark\s|Light\s|Alolan\s|Galarian\s|Hisuian\s|"
    r"Paldean\s|Radiant\s|Shining\s|Origin\s+Forme\s|"
    r"Rocket's\s|Team\s+Rocket's\s|Team\s+Magma's\s|Team\s+Aqua's\s|"
    r"N's\s|Hop's\s|Marnie's\s|Cynthia's\s|Lance's\s|Misty's\s|"
    r"Brock's\s|Sabrina's\s|Erika's\s|Blaine's\s|Koga's\s|Giovanni's\s|"
    r"Hau's\s|Iono's\s)"
)


def _base_pokemon_name(name: str) -> str:
    s = (name or "").strip()
    s = _PAREN_RE.sub("", s).strip()
    # Multiple passes because "Mega Charizard ex" → strip suffix →
    # "Mega Charizard" → strip prefix → "Charizard"
    for _ in range(3):
        prev = s
        s = _SUFFIX_RE.sub("", s).strip()
        s = _PREFIX_RE.sub("", s).strip()
        if s == prev:
            break
    return s


_POPULAR_POKEMON_CACHE: tuple[float, list[dict]] | None = None
_POPULAR_POKEMON_TTL_SEC = 3600


@router.get("/cards/popular-pokemon")
async def popular_pokemon(
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Top-N Pokémon by variant count, for the empty-search dropdown.

    The catalog has many cards per Pokémon (Charizard alone has 60+
    English printings spanning Base Set through Mega Evolution). For
    a "what should I search?" prompt, sorting by variant-richness
    surfaces the Pokémon users are most likely to actually be
    hunting — collector value tracks count more reliably than raw
    market price (a single SIR can swamp the list otherwise).

    Catalog scan is cached in-process for an hour; refreshed on the
    next request after expiry. The daily TCGCSV sync changes ranking
    glacially, so a fresh per-request scan adds nothing.
    """
    global _POPULAR_POKEMON_CACHE
    now = time.time()
    cached = _POPULAR_POKEMON_CACHE
    if cached and now - cached[0] < _POPULAR_POKEMON_TTL_SEC:
        return cached[1][:limit]

    rows = (
        await db.execute(
            select(Card.name, Card.image_small, Card.market_price_usd)
            .where(
                Card.supertype.in_(["Pokémon", "Pokemon"]),
                Card.language == "en",
            )
        )
    ).all()

    by_base: dict[str, dict] = {}
    for name, img, price in rows:
        base = _base_pokemon_name(name or "")
        if not base or len(base) > 32:
            continue
        e = by_base.setdefault(
            base,
            {"name": base, "count": 0, "image_small": None, "max_price": 0.0},
        )
        e["count"] += 1
        price_f = float(price) if price is not None else 0.0
        # Prefer the thumbnail of the variant priciest for visual
        # appeal — chase cards have nicer art than commons.
        if img and price_f >= e["max_price"]:
            e["image_small"] = img
            e["max_price"] = price_f
        elif img and not e["image_small"]:
            e["image_small"] = img

    ranked = sorted(
        by_base.values(),
        key=lambda d: (-d["count"], -d["max_price"]),
    )
    # Drop the residual max_price field — it was only a tiebreaker, not
    # something the client should display.
    cleaned = [
        {"name": d["name"], "count": d["count"], "image_small": d["image_small"]}
        for d in ranked
    ]
    _POPULAR_POKEMON_CACHE = (now, cleaned)
    return cleaned[:limit]


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


@router.get("/cards/{card_id}/graded-prices")
async def get_card_graded_prices(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    days: int = Query(90, ge=7, le=365),
) -> dict:
    """Latest median-per-grade for the graded tiles under the price
    chart. Reads `card_price_snapshots` filtered to grade rows, then
    walks a source-priority ladder when the same tier has multiple
    sources on the same day:
        ebay_sold   → actual clearing price (best)
        ebay_asking → Playwright active-listing fallback (labels as
                      "Asking" on the tile)
        ebay        → Browse API asking (oldest baseline)

    Response shape (matches `frontend/components/card/GradedPricesGrid.tsx`):
        {
          "psa10": {latest_price_usd, variant, source, updated_at, sales_count} | null,
          "psa9":  {...} | null,
          "cgc10": {...} | null,
          "cgc9":  {...} | null,
        }
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    ui_tiers = (
        "psa10", "psa9",
        "cgc10", "cgc9",
        "bgs10", "bgs10bl", "bgs9.5", "bgs9",
        # TAG Grading — newer service, especially hot on modern chases.
        "tag10", "tag9.5", "tag9",
    )
    from sqlalchemy import case

    source_priority = case(
        (CardPriceSnapshot.source == "ebay_sold", 0),
        (CardPriceSnapshot.source == "ebay_asking", 1),
        (CardPriceSnapshot.source == "ebay", 2),
        else_=3,
    )

    stmt = (
        select(
            CardPriceSnapshot.grade,
            CardPriceSnapshot.market_price_usd,
            CardPriceSnapshot.variant,
            CardPriceSnapshot.source,
            CardPriceSnapshot.snapshot_date,
            CardPriceSnapshot.sales_count,
        )
        .where(
            CardPriceSnapshot.card_id == card_id,
            CardPriceSnapshot.source.in_(("ebay", "ebay_sold", "ebay_asking")),
            CardPriceSnapshot.snapshot_date >= cutoff,
            CardPriceSnapshot.grade.in_(ui_tiers),
            CardPriceSnapshot.market_price_usd.is_not(None),
        )
        .order_by(
            CardPriceSnapshot.snapshot_date.desc(),
            source_priority.asc(),
        )
    )
    rows = (await db.execute(stmt)).all()

    # Keep only the most recent snapshot per grade (first hit wins
    # because we ordered by date desc + source priority so ebay_sold
    # beats ebay_asking beats ebay on same-day ties).
    latest: dict[str, dict] = {}
    for grade, price, variant, source, snap_date, sales_count in rows:
        if grade in latest:
            continue
        latest[grade] = {
            "latest_price_usd": float(price),
            "variant": variant,
            "source": source,
            "updated_at": snap_date,
            "sales_count": sales_count,
        }

    return {tier: latest.get(tier) for tier in ui_tiers}


# In-memory refresh cooldown so a single user can't fire the
# workflow 100× in a minute. Keyed by card_id → last-fire epoch.
# One-process only, but that's fine — Render runs one instance.
_REFRESH_LAST_FIRE: dict[str, float] = {}
# 5 min during beta while LO iterates on the data pipeline; bump
# back to 30 min once the fallback flow is validated end-to-end
# and we're worried about abuse rather than testing throughput.
_REFRESH_COOLDOWN_SECONDS = 60 * 5

# GitHub workflow_dispatch target for the "refresh one card" flow.
# The token needs `actions: write` scope on this repo. Set via
# GH_ACTIONS_TOKEN env var on Render — surfaced as a 503 if missing
# so the frontend can hide the button gracefully.
_GH_REFRESH_WORKFLOW_URL = (
    "https://api.github.com/repos/pulllistapp-stack/pulllist/"
    "actions/workflows/ebay-sold-refresh-one-card.yml/dispatches"
)


@router.post("/cards/{card_id}/refresh-graded-prices")
async def refresh_card_graded_prices(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> dict:
    """User-triggered refresh: fires the `ebay-sold-refresh-one-card`
    GH workflow via `workflow_dispatch` API. The workflow scrapes all
    4 grade tiers for this single card and writes new sold snapshots.
    Takes ~2-3 minutes end-to-end; caller should show a spinner and
    reload the card after a couple of minutes.

    Rate limits:
      * Card must exist (404 if not).
      * Signed-in only (401 if not). Prevents anonymous flood.
      * 30-minute cooldown per card_id across all users. Cheaper than
        per-user + card since PSA/CGC data doesn't change hour-to-hour.

    Returns:
      * 202 with `{status: "queued", cooldown_until: ts}` on success.
      * 429 if the cooldown is active — the client should display the
        remaining wait time.
      * 503 if the backend has no GH token configured (misconfig).
    """
    import os
    import time

    import httpx

    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")

    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    now = time.time()
    last = _REFRESH_LAST_FIRE.get(card_id, 0.0)
    if now - last < _REFRESH_COOLDOWN_SECONDS:
        wait = int(_REFRESH_COOLDOWN_SECONDS - (now - last))
        raise HTTPException(
            status_code=429,
            detail=f"Cooldown active for this card ({wait}s remaining)",
        )

    token = os.getenv("GH_ACTIONS_TOKEN")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Refresh not configured (missing GH_ACTIONS_TOKEN)",
        )

    payload = {
        "ref": "main",
        "inputs": {"card_id": card_id},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(_GH_REFRESH_WORKFLOW_URL, json=payload, headers=headers)
    if r.status_code >= 400:
        # 401 = bad token, 404 = wrong workflow, 422 = bad ref
        raise HTTPException(
            status_code=502,
            detail=f"GitHub dispatch failed: {r.status_code} {r.text[:200]}",
        )

    _REFRESH_LAST_FIRE[card_id] = now
    return {
        "status": "queued",
        "message": "Refresh queued — check back in 2-3 minutes",
        "cooldown_until": int(now + _REFRESH_COOLDOWN_SECONDS),
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
    max_price_usd: float | None = Query(
        None,
        ge=0,
        description=(
            "Price ceiling (both endpoints). Combined with min_price_usd "
            "this carves a band — e.g. min=5, max=30 surfaces movers "
            "between $5-$30 so a $480 chase doesn't dominate the same "
            "list as a $7 holo. Open-ended when omitted."
        ),
    ),
    min_abs_change_usd: float = Query(
        0.5,
        ge=0,
        description="Minimum absolute $ change between oldest and latest snapshot.",
    ),
    min_snapshots: int | None = Query(
        None,
        ge=2,
        le=60,
        description=(
            "Minimum snapshot count per (card, variant). Auto-scales with "
            "period_days when omitted (~40% coverage of the window) — "
            "5 for 7-day, 12 for 30-day, 36 for 90-day. Thin histories "
            "are TCGplayer's sticky-price artifacts, not real trends."
        ),
    ),
    max_mad_ratio: float = Query(
        0.6,
        ge=0,
        description=(
            "Max allowed MAD/median for the full window. Cards above this "
            "are too spiky to call 'trending' — usually a single $200 "
            "outlier sale sitting on top of a $30 flat history."
        ),
    ),
    tier: str = Query(
        "all",
        description=(
            "Rarity tier filter. 'bulk' = Common through Double Rare "
            "(pack-pull market). 'chase' = Ultra Rare and above plus "
            "promos (hunt cards). 'all' = no rarity filter."
        ),
        pattern="^(all|bulk|chase)$",
    ),
    era: str = Query(
        "all",
        description=(
            "Card-era filter. 'modern' = BW-onwards (Set.release_date "
            ">= 2011-03-01). 'classic' = pre-BW (WOTC / EX / DP / HGSS "
            "eras). 'all' = no era filter. BW-launch is the industry "
            "standard split — PSA/BGS vintage rules apply below it, "
            "and the modern card frame was introduced with BW."
        ),
        pattern="^(all|modern|classic)$",
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

    # Auto-scale snapshot floor to ~40% of the window when caller didn't
    # pin it. Vintage low-volume cards rarely have daily snapshots; they
    # only end up "trending" because the TCGplayer market-price algorithm
    # cooked one outlier listing into the public price. Requiring real
    # density flushes them out.
    #
    # Two cadences, two formulas — the wrong choice guts eBay trending:
    #   - TCGplayer prices via TCGCSV run daily; ~25% coverage of the
    #     window is realistic, cap 10 so 90d isn't empty for stable-
    #     price cards where our backfill only writes on movement.
    #   - eBay runs Mon + Thu pre-launch (see
    #     .github/workflows/daily-ebay-snapshot.yml). That's ~2/week,
    #     so a 7d window carries AT MOST 2 snapshots per card. Using
    #     the TCGplayer formula (floor=5) empties eBay 1d/7d/30d.
    #     Drop the floor to 2 and rescale.
    if min_snapshots is not None:
        effective_min_snapshots = min_snapshots
    elif source == "ebay":
        # 2 snapshots/week → require 2 minimum, cap 8 for 90d
        effective_min_snapshots = min(8, max(2, int(period_days * 0.10)))
    else:
        effective_min_snapshots = min(10, max(5, int(period_days * 0.25)))

    # eBay 1d rescue: a literal 24-hour window collides with the
    # Mon+Thu cron — most days there's no snapshot inside the
    # window at all, so the endpoint returns 0. Redefine 1d on
    # eBay as "since the previous snapshot" (typically 3-4 days
    # ago under Mon+Thu, next-day when the cron is daily again).
    # Honest label — users clicking 1d see whatever's changed
    # since our last sync, which is the useful signal here.
    cutoff = (date.today() - timedelta(days=period_days)).isoformat()
    if source == "ebay" and period_days == 1:
        # Filter to *substantial* snapshot days — a run that wrote only
        # a handful of rows is either the cron aborting early or one of
        # our manual probes, not the real Mon+Thu sweep. Anchoring 1d
        # on those stub days would collapse the eligible set to a
        # couple of cards. The 500-row floor sits comfortably above
        # any experimental partial run we've seen (~2-50 rows) and
        # well below a healthy full sweep (~3-4k rows).
        prev_two = (
            await db.execute(
                text(
                    "SELECT snapshot_date "
                    "FROM card_price_snapshots "
                    "WHERE source = :s "
                    "GROUP BY snapshot_date "
                    "HAVING COUNT(*) >= 500 "
                    "ORDER BY snapshot_date DESC LIMIT 2"
                ),
                {"s": source},
            )
        ).all()
        if len(prev_two) >= 2:
            prev_val = prev_two[1][0]
            cutoff = (
                prev_val.isoformat()
                if hasattr(prev_val, "isoformat") else str(prev_val)
            )

    # Aggregate to one row per (card_id, variant) at the SQL layer so
    # Python never sees the underlying ~280k snapshots. Postgres returns
    # the per-group price array already sorted by date; we only need to
    # slice the head/tail for the tercile medians. Cuts memory + wall
    # time enough to fit a 90d query into Render's 30s + 512MB envelope.
    tier_filter_sql = ""
    params: dict = {
        "source": source,
        "cutoff": cutoff,
        "min_snapshots": effective_min_snapshots,
    }
    if tier == "bulk":
        tier_filter_sql = "AND c.rarity = ANY(:tier_rarities)"
        params["tier_rarities"] = list(RARITY_BULK)
    elif tier == "chase":
        tier_filter_sql = "AND c.rarity = ANY(:tier_rarities)"
        params["tier_rarities"] = list(RARITY_CHASE)

    # Era filter piggybacks the same cards join. 2011-03-01 = BW launch
    # (US); the JP BW-era pair from Dec 2010 falls a couple months
    # short and gets bucketed as classic. Minor edge case — most users
    # care about the EN market side of the split.
    era_filter_sql = ""
    era_join_needed = False
    if era == "modern":
        era_filter_sql = "AND se.release_date >= DATE '2011-03-01'"
        era_join_needed = True
    elif era == "classic":
        era_filter_sql = "AND se.release_date < DATE '2011-03-01'"
        era_join_needed = True

    # Only JOIN cards / sets when we actually need them — saves a planner
    # pass on the much hotter tier='all' + era='all' default path.
    from_parts = ["FROM card_price_snapshots s"]
    if tier_filter_sql or era_join_needed:
        from_parts.append("JOIN cards c ON c.id = s.card_id")
    if era_join_needed:
        from_parts.append("JOIN sets se ON se.id = c.set_id")
    from_sql = " ".join(from_parts)
    agg_stmt = text(
        f"""
        SELECT s.card_id, s.variant,
               array_agg(s.market_price_usd ORDER BY s.snapshot_date) AS prices
        {from_sql}
        WHERE s.source = :source
          AND s.snapshot_date >= :cutoff
          AND s.market_price_usd IS NOT NULL
          {tier_filter_sql}
          {era_filter_sql}
        GROUP BY s.card_id, s.variant
        HAVING count(*) >= :min_snapshots
        """
    )
    by_card_variant: dict[tuple[str, str], list[float]] = {}
    for card_id, variant, prices in (
        await db.execute(agg_stmt, params)
    ).all():
        by_card_variant[(card_id, variant)] = [float(p) for p in prices]

    best_per_card: dict[str, dict] = {}
    for (card_id, variant), prices in by_card_variant.items():
        if len(prices) < effective_min_snapshots:
            continue
        # Bubble guard 1 — full-window spread. A flat $30 series with one
        # bad $240 sale at the end has MAD/median around 0.7+; we treat that
        # as noise instead of a "trend".
        if _mad_ratio(prices) > max_mad_ratio:
            continue
        # Use median of the first and last thirds (or first/last snapshot
        # if we have too few) as baseline + current. Single-point comparison
        # against snaps[0]/snaps[-1] gets blown up by ONE bad backfilled
        # value - a card going from a spurious $5 baseline to $200 reads
        # as +3900% when the real move is +30%. Tercile medians shrug off
        # one outlier per side.
        third = max(1, len(prices) // 3)
        oldest_window = prices[:third]
        latest_window = prices[-third:]
        middle_window = prices[third:-third] if len(prices) >= 3 * third else prices[third:third + max(1, third)]
        # Bubble guard 2 — single-point spike inside the latest tercile.
        # Median is robust to one outlier in a tercile of 5+, but for the
        # 3- or 4-point terciles we get from a one-week window, a lone
        # spike still drags the median up. Drop the card if it's there.
        if _has_lone_spike(latest_window):
            continue
        oldest = _median(oldest_window)
        latest = _median(latest_window)
        middle = _median(middle_window) if middle_window else None
        if oldest is None or latest is None or oldest <= 0:
            continue
        # Bubble guard 3 — step function detector. A real trending card
        # transitions gradually: middle tercile lands somewhere between
        # oldest and latest. A bubble is "flat for months → sudden spike
        # at the end" — middle stays close to oldest while latest jumps.
        # TCGplayer's market-price algorithm is sticky after one outlier
        # sale, so it sits at the inflated level for many snapshots and
        # tricks tercile-median into reporting the move as legitimate.
        if middle is not None and len(prices) >= 6:
            span = latest - oldest
            if abs(span) >= 0.01:
                # Fraction of the move that happened by the middle tercile.
                # Below 0.3 means the spike is tail-loaded enough to look
                # like a step function; a real trend has 30%+ of the move
                # already happened by mid-window.
                progress = (middle - oldest) / span
                if progress < 0.3:
                    continue
        # Quality floors - both endpoints must clear the price floor AND the
        # absolute change must be meaningful.
        if float(oldest) < min_price_usd or float(latest) < min_price_usd:
            continue
        if max_price_usd is not None and (
            float(oldest) > max_price_usd or float(latest) > max_price_usd
        ):
            continue
        if abs(float(latest) - float(oldest)) < min_abs_change_usd:
            continue
        delta_pct = ((latest - oldest) / oldest) * 100.0
        # Cap displayed % at +/-200 - in our experience anything bigger
        # than this is either a sparse-snapshot artifact or a TCGplayer
        # listing-price spike with no real sales behind it. The few real
        # +300% moves we lose are worth the trust we keep by not running
        # bubbly #1s on the trending page.
        if abs(delta_pct) > 200:
            continue
        entry = {
            "card_id": card_id,
            "variant": variant,
            "latest_price": float(latest),
            "oldest_price": float(oldest),
            "delta_pct": delta_pct,
            "snapshots_count": len(prices),
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

    Uses the same noise-filtered query as the snapshot script. Runs the
    default relevance query PLUS a slab-focused variant so the Graded
    tab in the frontend LiveListings component actually populates —
    eBay Browse's default ranking for a bare "card name + number" query
    returns almost exclusively raw listings; slabs only surface when
    the query contains an explicit grader token. Frontend cache is
    ~5min per card so the 2 API calls don't run on every navigation.
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

    # Over-fetch so the post-filter has headroom. eBay's fuzzy keyword
    # match routinely returns 3-5 different print variants of the same
    # Pokemon in a single page — at limit=12, after we drop wrong-number
    # listings we can land at 3-4 actual matches. Pulling 3x gives the
    # strict filter room to breathe without changing the user-facing limit.
    raw_limit = min(limit * 3, 60)

    try:
        async with EbayClient() as ebay:
            raw_result, graded_result = await asyncio.gather(
                ebay.browse_search(
                    query,
                    limit=raw_limit,
                    category_id=POKEMON_CATEGORIES["tcg_root"],
                ),
                # Slab pass — appending " PSA" surfaces PSA-graded
                # slabs (the dominant grading company by listing
                # volume). CGC / BGS titles also frequently include
                # "PSA" as a comparison ("PSA 10 equiv") so this
                # single suffix catches most of them too. If it
                # doesn't, users can still find those via TCG search.
                ebay.browse_search(
                    f"{query} PSA",
                    limit=raw_limit,
                    category_id=POKEMON_CATEGORIES["tcg_root"],
                ),
                return_exceptions=True,
            )
    except EbayClientError as e:
        return {"listings": [], "query": query, "error": str(e)}
    except Exception as e:
        return {"listings": [], "query": query, "error": f"unexpected: {e}"}

    # Combine + dedupe by URL. Same listing sometimes surfaces in both
    # passes (rare: a slab whose title also passes the raw query).
    raw_items: list[dict] = []
    seen_urls: set[str] = set()
    for res in (raw_result, graded_result):
        if isinstance(res, Exception):
            continue
        if not isinstance(res, dict):
            continue
        for it in res.get("itemSummaries") or []:
            url = it.get("itemWebUrl") or it.get("itemHref")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            raw_items.append(it)
    # Strict card-number match: drop listings whose titles reference a
    # different x/y than this card. See app/services/listing_match.py
    # for the tier breakdown. Wishlist alerts (future) will tighten this
    # to score == 100 only; for the live panel >= 70 is comfortable.
    printed_total = set_obj.printed_total if set_obj else None
    filtered_items, dropped = filter_listings(
        raw_items,
        card_number=card.number,
        printed_total=printed_total,
        min_score=70,
    )
    # Fallback for vintage / promo cards. Sellers of Nintendo Black Star
    # Promos, POP Series, e-Reader promos etc. routinely list the card
    # by name alone ("Pokemon Mudkip Nintendo Black Star Promo NM"),
    # without the "5/53" pattern — those listings score 30 ("no
    # card-number reference") and the 70 threshold drops every one.
    # Retry at 30 only when the strict pass found nothing; modern set
    # cards never enter this branch because their listings carry the
    # x/y format and pass at 70+. score 0 (DIFFERENT card-number in
    # title) is still rejected — we never knowingly surface a wrong
    # print.
    if not filtered_items and raw_items:
        filtered_items, dropped = filter_listings(
            raw_items,
            card_number=card.number,
            printed_total=printed_total,
            min_score=30,
        )

    listings = []
    dropped_outlier_low = 0
    for it in filtered_items:
        if len(listings) >= limit:
            break
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
            # Bait-scam guard: high-value cards (≥$50 ref) listed at
            # <25% of reference are almost always stolen-photo scams or
            # mistitled junk ("DIY", "Mystery Grab", custom prints).
            # The DIY/Mystery title scrub happens upstream in
            # filter_listings, but plenty of scams use plain-looking
            # titles ("Pokemon Rayquaza VMAX 218/203 NM") with a
            # $9.99 ask — that's where this guard matters.
            total_usd_check = price_v + ship_cost
            if is_low_outlier_price(total_usd_check, card.market_price_usd):
                dropped_outlier_low += 1
                continue
            seller = it.get("seller") or {}
            # eBay returns `image.imageUrl` for full image + `thumbnailImages[]`
            # for smaller renderable URLs. Prefer thumbnail (CDN-optimized).
            img = it.get("image") or {}
            thumbs = it.get("thumbnailImages") or []
            image_url = (
                (thumbs[0].get("imageUrl") if thumbs else None)
                or img.get("imageUrl")
            )

            # Seller trust tier — feedbackScore is the total transaction
            # count, feedbackPercentage the positive-rating percent.
            raw_score = seller.get("feedbackScore")
            try:
                seller_score = int(raw_score) if raw_score is not None else None
            except (TypeError, ValueError):
                seller_score = None
            raw_pct = seller.get("feedbackPercentage")
            try:
                seller_pct = float(raw_pct) if raw_pct is not None else None
            except (TypeError, ValueError):
                seller_pct = None
            trust = seller_trust_tier(seller_score, seller_pct)
            total_usd = price_v + ship_cost
            sus = is_suspicious(total_usd, card.market_price_usd, trust)

            listings.append({
                "title": (it.get("title") or "")[:180],
                "price_usd": price_v,
                "shipping_usd": ship_cost,
                "total_usd": total_usd,
                "condition": it.get("condition") or "Ungraded",
                "seller": seller.get("username") or "?",
                "seller_feedback_pct": seller_pct,
                "seller_feedback_score": seller_score,
                "seller_trust_tier": trust,
                "suspicious": sus,
                "url": it.get("itemWebUrl") or "",
                "image_url": image_url,
                "source": "eBay",
            })
        except Exception:
            continue

    # Sort: clean listings first (by price ascending), then suspicious ones
    # at the bottom (also by price). Keeps the "Cheapest" tile on a real
    # match instead of a scam decoy.
    listings.sort(key=lambda x: (x["suspicious"], x["total_usd"]))
    return {
        "listings": listings,
        "query": query,
        "count": len(listings),
        # Surfaced for the frontend so we can show "X listings hidden as
        # different prints of this card" if we ever want a peek-back UI.
        "filter": {
            "min_score": 70,
            "raw_count": len(raw_items),
            "dropped_other_print": dropped.get("different_print", 0),
            "dropped_no_pattern": dropped.get("no_pattern", 0),
            "dropped_accessory": dropped.get("accessory", 0),
            "dropped_outlier_low": dropped_outlier_low,
        },
    }


# ────────── Single-card price refresh ──────────
#
# Per-card in-memory cooldown: blocks rapid repeat clicks across all
# users so a viral card doesn't shell-out the eBay quota in seconds.
# Single-instance Render free-tier — global to the process is fine.
_REFRESH_LAST_TS: dict[str, float] = {}
_REFRESH_COOLDOWN_SEC = 60


@router.post("/cards/{card_id}/refresh-price")
async def refresh_card_price(
    card_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-fetch eBay pricing for a single card on demand. Hit when a
    user clicks the 🔄 refresh button on the card detail page.

    Per-card cooldown is 60s globally — repeated clicks within the
    window return the existing snapshot without re-hitting eBay. The
    UX intent (per `feedback-hide-staleness`) is for the user to see
    a transient "Up to date!" indicator on every click; we make that
    truthful by reporting `cached: true` so the frontend can still
    flash the indicator without lying about a backend refresh.
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    now_ts = time.time()
    last_ts = _REFRESH_LAST_TS.get(card_id, 0.0)
    cached = (now_ts - last_ts) < _REFRESH_COOLDOWN_SEC

    if not cached:
        _REFRESH_LAST_TS[card_id] = now_ts
        set_obj = await db.get(Set, card.set_id) if card.set_id else None
        query = build_card_query(
            card_name=card.name,
            card_number=card.number,
            printed_total=set_obj.printed_total if set_obj else None,
            set_name=set_obj.name if set_obj else None,
            rarity=card.rarity,
        )
        reference_price = (
            float(card.market_price_usd)
            if card.market_price_usd is not None
            else None
        )
        try:
            async with EbayClient() as ebay:
                detail = await ebay.price_summary_with_trace(
                    query,
                    max_results=50,
                    reference_price_usd=reference_price,
                    card_number=card.number,
                    rarity=card.rarity,
                )
        except EbayClientError:
            # Quota / network failure — return what we have, mark cached
            # so the UI still flashes "Up to date!" (no lie — we tried).
            return {
                "card_id": card_id,
                "market_price_usd": card.market_price_usd,
                "ebay_median": None,
                "cached": True,
            }
        except Exception:
            return {
                "card_id": card_id,
                "market_price_usd": card.market_price_usd,
                "ebay_median": None,
                "cached": True,
            }

        summary = detail.get("summary")
        if summary:
            snapshot_date = date.today().isoformat()
            ebay_median = float(summary["median"])
            row = {
                "card_id": card_id,
                "source": "ebay",
                "variant": "active",
                "market_price_usd": ebay_median,
                "low_price_usd": float(summary["low"]),
                "mid_price_usd": ebay_median,
                "high_price_usd": float(summary["high"]),
                "sales_count": None,
                "snapshot_at": datetime.utcnow(),
                "snapshot_date": snapshot_date,
            }
            dialect_name = db.bind.dialect.name
            insert_cls = (
                pg_insert if dialect_name == "postgresql" else sqlite_insert
            )
            upsert_stmt = (
                insert_cls(CardPriceSnapshot)
                .values(**row)
                .on_conflict_do_update(
                    index_elements=["card_id", "source", "variant", "grade", "snapshot_date"],
                    set_={
                        "market_price_usd": row["market_price_usd"],
                        "low_price_usd": row["low_price_usd"],
                        "mid_price_usd": row["mid_price_usd"],
                        "high_price_usd": row["high_price_usd"],
                        "snapshot_at": row["snapshot_at"],
                    },
                )
            )
            await db.execute(upsert_stmt)
            await db.commit()

    # Return the latest snapshot for both sources so the frontend can
    # display the freshest numbers without doing a second round-trip.
    latest_stmt = (
        select(CardPriceSnapshot)
        .where(CardPriceSnapshot.card_id == card_id)
        .order_by(CardPriceSnapshot.snapshot_at.desc())
    )
    latest_rows = (await db.execute(latest_stmt)).scalars().all()
    tcg_market: float | None = None
    ebay_median: float | None = None
    for snap in latest_rows:
        if snap.source == "tcgplayer" and tcg_market is None:
            tcg_market = (
                float(snap.market_price_usd)
                if snap.market_price_usd is not None
                else None
            )
        elif snap.source == "ebay" and ebay_median is None:
            ebay_median = (
                float(snap.market_price_usd)
                if snap.market_price_usd is not None
                else None
            )
        if tcg_market is not None and ebay_median is not None:
            break

    # The headline "market price" uses the same averaging rule the
    # card hero shows on first paint.
    if tcg_market is not None and ebay_median is not None:
        market_price = (tcg_market + ebay_median) / 2
    else:
        market_price = tcg_market if tcg_market is not None else ebay_median

    return {
        "card_id": card_id,
        "market_price_usd": market_price,
        "tcg_market": tcg_market,
        "ebay_median": ebay_median,
        "cached": cached,
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

