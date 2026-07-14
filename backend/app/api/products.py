"""Sealed product routes — list, detail, and per-set browsing plus a
rough EV (expected value) estimate for booster boxes and packs.

EV methodology (deliberately conservative for MVP):
    * Compute average market_price_usd per rarity bucket within the
      product's set.
    * Model a modern SV-era booster pack as
        6 Common + 3 Uncommon + 1 foil slot + 1 reverse-holo slot.
    * Foil slot distribution (rough long-run averages):
        Rare Holo         65%
        Double Rare       18%
        Illustration Rare  7%
        Ultra Rare         5%
        Hyper Rare         2%
        Special IR         3%
    * Reverse-holo slot ≈ 2× a random common's value (thin heuristic —
      real reverse holos map to the specific card, but at MVP we're
      averaging the set).

Box EV = pack EV × packs_per_box. ETBs add a flat +$10 accessory
allowance to reflect sleeves + dice + damage counters. This is a
first-pass model; the UI labels it "Est." so users don't take it as
gospel.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Card, Product, ProductPriceSnapshot, Set


router = APIRouter(prefix="/products", tags=["products"])


# Sealed products change ~daily at most (TCGCSV cron). 5-min shared
# cache with 10-min stale-while-revalidate cuts Neon compute + egress
# without meaningfully aging the data. Vercel + Render both honor
# s-maxage on their edge, so this survives even a cold backend.
_CATALOG_CACHE = "public, s-maxage=300, stale-while-revalidate=600"


VALID_TYPES = {
    "booster_box",
    "etb",
    "booster_bundle",
    "premium_collection",
    "tin",
    "blister",
    "build_battle",
    "sleeved_booster",
    "other",
}


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    set_id: str | None
    set_name: str | None
    product_type: str
    packs_per_box: int | None
    tcgplayer_product_id: int | None
    market_price_usd: float | None
    low_price_usd: float | None
    high_price_usd: float | None
    msrp_usd: float | None
    image_url: str | None
    tcgplayer_url: str | None


class ProductEV(BaseModel):
    pack_ev_usd: float | None
    box_ev_usd: float | None
    packs_used: int | None
    """Number of packs the EV assumes — 0/null for non-pack products."""
    market_price_usd: float | None
    """Current sealed market price — echoed for the "vs EV" chip."""
    premium_pct: float | None
    """(market - box_ev) / box_ev × 100. Positive = sealed premium
    (paying to keep sealed), negative = "cracking pays"."""


class ProductDetail(ProductRead):
    ev: ProductEV | None
    description: str | None


def _row_to_read(row: Product, set_name: str | None) -> ProductRead:
    return ProductRead(
        id=row.id,
        name=row.name,
        set_id=row.set_id,
        set_name=set_name,
        product_type=row.product_type,
        packs_per_box=row.packs_per_box,
        tcgplayer_product_id=row.tcgplayer_product_id,
        market_price_usd=row.market_price_usd,
        low_price_usd=row.low_price_usd,
        high_price_usd=row.high_price_usd,
        msrp_usd=row.msrp_usd,
        image_url=row.image_url,
        tcgplayer_url=row.tcgplayer_url,
    )


# Foil-slot mix for a modern SV-era pack. Percentages roughly reflect
# long-run pull observations; not an official Pokemon Company number.
_FOIL_MIX = [
    ("Rare Holo", 0.65),
    ("Double Rare", 0.18),
    ("Illustration Rare", 0.07),
    ("Ultra Rare", 0.05),
    ("Special Illustration Rare", 0.03),
    ("Hyper Rare", 0.02),
]

# Any card whose rarity contains one of these strings gets rolled into
# that bucket. Case-insensitive substring match.
_BUCKET_ALIASES: dict[str, tuple[str, ...]] = {
    "Common": ("common",),
    "Uncommon": ("uncommon",),
    "Rare Holo": ("rare holo",),
    "Double Rare": ("double rare",),
    "Illustration Rare": ("illustration rare",),
    "Ultra Rare": ("ultra rare", "rare ultra"),
    "Hyper Rare": ("hyper rare", "rare rainbow", "rare secret"),
    "Special Illustration Rare": ("special illustration rare",),
}

_ETB_ACCESSORY_USD = 10.0  # sleeves + dice + damage counters


async def _compute_ev(
    db: AsyncSession, row: Product
) -> ProductEV | None:
    """Best-effort EV. Requires set_id + packs_per_box; otherwise the
    frontend hides the widget."""
    if not row.set_id or not row.packs_per_box:
        return None

    stmt = select(Card.rarity, Card.market_price_usd).where(
        and_(Card.set_id == row.set_id, Card.market_price_usd.isnot(None))
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return None

    # Bucket by rarity → collect prices.
    buckets: dict[str, list[float]] = {k: [] for k in _BUCKET_ALIASES}
    for rarity, price in rows:
        if rarity is None:
            continue
        r = rarity.lower()
        for bucket, keys in _BUCKET_ALIASES.items():
            if any(k in r for k in keys):
                buckets[bucket].append(float(price))
                break

    def avg(bucket: str) -> float:
        vals = buckets.get(bucket) or []
        return sum(vals) / len(vals) if vals else 0.0

    common_avg = avg("Common")
    uncommon_avg = avg("Uncommon")
    foil_ev = sum(avg(bucket) * weight for bucket, weight in _FOIL_MIX)
    reverse_ev = common_avg * 2.0  # cheap heuristic

    pack_ev = (
        6 * common_avg
        + 3 * uncommon_avg
        + foil_ev
        + reverse_ev
    )

    packs = row.packs_per_box
    accessory = _ETB_ACCESSORY_USD if row.product_type == "etb" else 0.0
    box_ev = pack_ev * packs + accessory

    market = row.market_price_usd
    premium_pct: float | None = None
    if market and box_ev > 0:
        premium_pct = (market - box_ev) / box_ev * 100

    return ProductEV(
        pack_ev_usd=round(pack_ev, 2) if pack_ev > 0 else None,
        box_ev_usd=round(box_ev, 2) if box_ev > 0 else None,
        packs_used=packs,
        market_price_usd=market,
        premium_pct=round(premium_pct, 1) if premium_pct is not None else None,
    )


@router.get("", response_model=dict)
async def list_products(
    response: Response,
    set_id: str | None = Query(None),
    product_type: str | None = Query(None),
    sort: str = Query("newest", pattern="^(newest|price_desc|price_asc|name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Browse sealed products. Optional filters: set_id / product_type.
    Sort: newest (default, via set release_date desc + created_at) /
    price_desc / price_asc / name."""
    if product_type and product_type not in VALID_TYPES:
        raise HTTPException(400, f"product_type must be one of {sorted(VALID_TYPES)}")

    base = select(Product, Set.name, Set.release_date).outerjoin(
        Set, Product.set_id == Set.id
    )
    if set_id:
        base = base.where(Product.set_id == set_id)
    if product_type:
        base = base.where(Product.product_type == product_type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    if sort == "price_desc":
        base = base.order_by(Product.market_price_usd.desc().nullslast())
    elif sort == "price_asc":
        base = base.order_by(Product.market_price_usd.asc().nullsfirst())
    elif sort == "name":
        base = base.order_by(Product.name.asc())
    else:
        base = base.order_by(
            Set.release_date.desc().nullslast(),
            Product.created_at.desc(),
        )

    base = base.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(base)).all()

    response.headers["Cache-Control"] = _CATALOG_CACHE
    return {
        "items": [_row_to_read(p, sn).model_dump() for p, sn, _ in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ProductDetail:
    row = await db.get(Product, product_id)
    if row is None:
        raise HTTPException(404, "Product not found")
    set_row = await db.get(Set, row.set_id) if row.set_id else None
    ev = await _compute_ev(db, row)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return ProductDetail(
        **_row_to_read(row, set_row.name if set_row else None).model_dump(),
        ev=ev,
        description=row.description,
    )


@router.get("/{product_id}/history", response_model=dict)
async def get_product_history(
    product_id: str,
    response: Response,
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Daily price history for the sealed product's `market_price_usd`.
    Backs the chart on the product detail page. Matches the card-side
    /cards/{id}/history shape so the frontend chart component can be
    reused with minimal glue."""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    stmt = (
        select(
            ProductPriceSnapshot.snapshot_date,
            ProductPriceSnapshot.market_price_usd,
            ProductPriceSnapshot.low_price_usd,
            ProductPriceSnapshot.mid_price_usd,
            ProductPriceSnapshot.high_price_usd,
        )
        .where(
            ProductPriceSnapshot.product_id == product_id,
            ProductPriceSnapshot.snapshot_date >= cutoff,
        )
        .order_by(ProductPriceSnapshot.snapshot_date.asc())
    )
    rows = (await db.execute(stmt)).all()

    points = [
        {
            "date": snap_date,
            "market": float(market) if market is not None else None,
            "low": float(low) if low is not None else None,
            "mid": float(mid) if mid is not None else None,
            "high": float(high) if high is not None else None,
        }
        for snap_date, market, low, mid, high in rows
    ]

    # Same catalog cache TTL as the browse endpoints — sealed snapshots
    # only refresh once a day.
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return {
        "product_id": product_id,
        "product_name": product.name,
        "days": days,
        "points": points,
    }


@router.get("/set/{set_id}/list", response_model=list[ProductRead])
async def list_products_for_set(
    set_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> list[ProductRead]:
    """All sealed products for a set — used by /sets/[id] page's
    'Sealed products' section. Ordered by price desc so the big-ticket
    Booster Box / ETB Case land first."""
    s = await db.get(Set, set_id)
    if s is None:
        raise HTTPException(404, "Set not found")
    rows = (
        await db.execute(
            select(Product)
            .where(Product.set_id == set_id)
            .order_by(Product.market_price_usd.desc().nullslast())
        )
    ).scalars().all()
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return [_row_to_read(p, s.name) for p in rows]
