from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import Card, CardPriceSnapshot, CollectionItem, Set, User
from app.schemas.card import CardList, CardRead
from app.schemas.set import SetRead, SetWithCardCount
from app.services.ebay_client import POKEMON_CATEGORIES, EbayClient, EbayClientError, build_card_query
from app.services.listing_match import filter_listings, is_suspicious, seller_trust_tier

router = APIRouter()


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
        )
        .outerjoin(Card, Card.set_id == Set.id)
        .where(Set.language == language)
        .group_by(Set.id)
        .order_by(Set.release_date.desc().nullslast())
    )
    if series:
        stmt = stmt.where(Set.series == series)

    # JP region default: hide sets that don't have a logo, but exempt
    # the promo eras (JPP-*) which intentionally have no logo - those
    # are virtual buckets that group promo cards. Combined: every JP
    # row visible to users is either a logo'd expansion or a promo era
    # bucket with at least one card under it.
    if language == "ja":
        stmt = stmt.where(
            (Set.logo_url.is_not(None)) | (Set.id.like("JPP-%"))
        )

    rows = (await db.execute(stmt)).all()

    # For JP, hide promo eras that ended up with zero cards (old eras
    # like PCG-P, ADV-P, World Collection — we have set rows but no
    # source provides card data for them). A logo'd expansion with zero
    # cards stays visible: that's a content gap worth surfacing.
    if language == "ja":
        rows = [r for r in rows if not (r[0].id.startswith("JPP-") and r[1] == 0)]

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
        if not dex_list:
            continue
        for n in dex_list:
            try:
                dex_set.add(int(n))
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
    stmt = (
        stmt
        # Prefer exact name hits over dex-only cross-language matches so a
        # user searching "Charizard" still sees the EN cards first; JP cards
        # with the same dex number follow.
        .order_by(
            Card.name.ilike(pattern).desc(),
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
    # TCGplayer prices update ~weekly via pokemontcg.io. The 25% coverage
    # ratio works for 7d/30d but overshoots at 90d (a stable card may only
    # generate 8-12 snapshots over 90 days even though it's heavily traded
    # — our backfill only writes when the price moves). Cap the floor at
    # 10 so 90d isn't an empty page.
    effective_min_snapshots = (
        min_snapshots if min_snapshots is not None
        else min(10, max(5, int(period_days * 0.25)))
    )

    cutoff = (date.today() - timedelta(days=period_days)).isoformat()

    # Aggregate to one row per (card_id, variant) at the SQL layer so
    # Python never sees the underlying ~280k snapshots. Postgres returns
    # the per-group price array already sorted by date; we only need to
    # slice the head/tail for the tercile medians. Cuts memory + wall
    # time enough to fit a 90d query into Render's 30s + 512MB envelope.
    from sqlalchemy import text  # local import - rarely-used helper
    agg_stmt = text(
        """
        SELECT card_id, variant,
               array_agg(market_price_usd ORDER BY snapshot_date) AS prices
        FROM card_price_snapshots
        WHERE source = :source
          AND snapshot_date >= :cutoff
          AND market_price_usd IS NOT NULL
        GROUP BY card_id, variant
        HAVING count(*) >= :min_snapshots
        """
    )
    by_card_variant: dict[tuple[str, str], list[float]] = {}
    for card_id, variant, prices in (
        await db.execute(
            agg_stmt,
            {"source": source, "cutoff": cutoff, "min_snapshots": effective_min_snapshots},
        )
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

    # Over-fetch so the post-filter has headroom. eBay's fuzzy keyword
    # match routinely returns 3-5 different print variants of the same
    # Pokemon in a single page — at limit=12, after we drop wrong-number
    # listings we can land at 3-4 actual matches. Pulling 3x gives the
    # strict filter room to breathe without changing the user-facing limit.
    raw_limit = min(limit * 3, 60)

    try:
        async with EbayClient() as ebay:
            result = await ebay.browse_search(
                query,
                limit=raw_limit,
                category_id=POKEMON_CATEGORIES["tcg_root"],
            )
    except EbayClientError as e:
        return {"listings": [], "query": query, "error": str(e)}
    except Exception as e:
        return {"listings": [], "query": query, "error": f"unexpected: {e}"}

    raw_items = result.get("itemSummaries") or []
    # Strict card-number match: drop listings whose titles reference a
    # different x/y than this card. See app/services/listing_match.py
    # for the tier breakdown. Wishlist alerts (future) will tighten this
    # to score == 100 only; for the live panel >= 70 is comfortable.
    filtered_items, dropped = filter_listings(
        raw_items,
        card_number=card.number,
        printed_total=set_obj.printed_total if set_obj else None,
        min_score=70,
    )

    listings = []
    for it in filtered_items[:limit]:
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
        },
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
