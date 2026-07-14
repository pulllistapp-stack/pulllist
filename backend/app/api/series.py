"""Series-level browse endpoints.

`Set.series` groups related sets into an era ("Scarlet & Violet",
"Sword & Shield", ...). Users navigating from the /sets browse already
see series headers, but there's no landing page per series where all
the sets + sealed products for that era live side-by-side. These
endpoints back the `/series/[slug]` route.

Slugging: series names become URL-safe by lowercase → collapse
non-alphanumerics to `-`. Ambiguity is unlikely (there aren't two
"Scarlet & Violet" series), and we match by comparing the slugged
form on the server side so URLs stay stable when set counts change.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Card, Product, Set


router = APIRouter(prefix="/series", tags=["series"])


_CATALOG_CACHE = "public, s-maxage=300, stale-while-revalidate=600"


def _slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


@router.get("", response_model=dict)
async def list_series(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Every distinct series (EN only for now) with aggregate counts
    per series — sets, cards, sealed products, latest release date.
    Feeds the /series index page (future) and any nav dropdown."""
    rows = (
        await db.execute(
            select(
                Set.series,
                func.count(distinct(Set.id)).label("set_count"),
                func.max(Set.release_date).label("latest_release"),
            )
            .where(Set.series.is_not(None), Set.language == "en")
            .group_by(Set.series)
            .order_by(func.max(Set.release_date).desc().nullslast())
        )
    ).all()

    # Card + product counts per series in one round trip each.
    card_counts = dict(
        (
            await db.execute(
                select(Set.series, func.count(Card.id))
                .join(Card, Card.set_id == Set.id)
                .where(Set.language == "en", Set.series.is_not(None))
                .group_by(Set.series)
            )
        ).all()
    )
    product_counts = dict(
        (
            await db.execute(
                select(Set.series, func.count(Product.id))
                .join(Product, Product.set_id == Set.id)
                .where(Set.language == "en", Set.series.is_not(None))
                .group_by(Set.series)
            )
        ).all()
    )

    response.headers["Cache-Control"] = _CATALOG_CACHE
    return {
        "items": [
            {
                "series": series,
                "slug": _slugify(series),
                "set_count": int(set_count),
                "card_count": int(card_counts.get(series, 0)),
                "product_count": int(product_counts.get(series, 0)),
                "latest_release": (
                    latest_release.isoformat() if latest_release else None
                ),
            }
            for series, set_count, latest_release in rows
        ]
    }


@router.get("/{slug}", response_model=dict)
async def get_series(
    slug: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Series detail — includes every set in the series (newest first),
    every sealed product across those sets, and headline totals so the
    /series/[slug] page can render its header without a follow-up call."""
    # Fetch every EN series once, slug-compare in Python. This keeps
    # the URL scheme stable even if a series is later renamed in the
    # catalog (edge case; historical URLs still resolve as long as the
    # slug matches at check time).
    all_series = (
        await db.execute(
            select(Set.series)
            .where(Set.series.is_not(None), Set.language == "en")
            .distinct()
        )
    ).scalars().all()

    match = next((s for s in all_series if _slugify(s) == slug), None)
    if match is None:
        raise HTTPException(404, "Series not found")

    sets = (
        await db.execute(
            select(Set)
            .where(Set.series == match, Set.language == "en")
            .order_by(Set.release_date.desc().nullslast())
        )
    ).scalars().all()
    set_ids = [s.id for s in sets]

    # Per-set card counts in one query.
    card_counts_rows = (
        await db.execute(
            select(Card.set_id, func.count(Card.id))
            .where(Card.set_id.in_(set_ids) if set_ids else False)
            .group_by(Card.set_id)
        )
    ).all()
    card_counts = {sid: int(n) for sid, n in card_counts_rows}

    # Every sealed product for these sets — the /series page renders
    # them below the sets grid so buyers can see the whole era's
    # sealed lineup at once.
    products = (
        (
            await db.execute(
                select(Product)
                .where(Product.set_id.in_(set_ids) if set_ids else False)
                .order_by(Product.market_price_usd.desc().nullslast())
            )
        ).scalars().all()
        if set_ids
        else []
    )

    total_cards = sum(card_counts.values())

    def _set_payload(s: Set) -> dict[str, Any]:
        return {
            "id": s.id,
            "name": s.name,
            "release_date": s.release_date.isoformat() if s.release_date else None,
            "printed_total": s.printed_total,
            "total": s.total,
            "logo_url": s.logo_url,
            "symbol_url": s.symbol_url,
            "card_count": card_counts.get(s.id, 0),
        }

    def _product_payload(p: Product) -> dict[str, Any]:
        return {
            "id": p.id,
            "name": p.name,
            "set_id": p.set_id,
            "product_type": p.product_type,
            "market_price_usd": p.market_price_usd,
            "image_url": p.image_url,
            "tcgplayer_url": p.tcgplayer_url,
        }

    response.headers["Cache-Control"] = _CATALOG_CACHE
    return {
        "series": match,
        "slug": slug,
        "set_count": len(sets),
        "card_count": total_cards,
        "product_count": len(products),
        "sets": [_set_payload(s) for s in sets],
        "products": [_product_payload(p) for p in products],
    }
