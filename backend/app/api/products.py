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
from app.services.ebay_client import EbayClient, EbayClientError


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
    include_unpriced: bool = Query(
        False,
        description=(
            "Include products missing a TCGCSV market price. Default false — "
            "the browse grid stays clean; the ~14% of SKUs without a price "
            "usually mean TCGCSV hasn't listed sold inventory in the last "
            "week (obscure McDonald's promos, old regional exclusives, etc.)."
        ),
    ),
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
    if not include_unpriced:
        # 14% of the catalog carries no market price (TCGCSV hasn't
        # listed sold inventory recently, or the SKU is a McDonald's
        # promo pack / obscure regional exclusive). Show `—` tiles by
        # default clutters the grid; opt-in via ?include_unpriced=1.
        base = base.where(Product.market_price_usd.is_not(None))

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


# Per-product refresh cooldown, keyed by product_id → last-fire epoch.
# 5 minutes covers accidental double-taps but stays generous — sealed
# TCGCSV prices only move once a day so anything below 5 min would
# hammer the upstream feed without changing the number.
_PRODUCT_REFRESH_LAST_FIRE: dict[str, float] = {}
_PRODUCT_REFRESH_COOLDOWN_SECONDS = 60 * 5

_TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
_POKEMON_CATEGORY_ID = 3
_TCGCSV_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


@router.post("/{product_id}/refresh", response_model=dict)
async def refresh_product_price(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Pull fresh TCGCSV prices for one sealed product on demand.

    Sealed products don't have the graded-tier + eBay ladder that
    singles carry, so the refresh is one HTTP call — fetch the
    product's group prices from TCGCSV, pluck our productId, write
    back to the Product row + insert today's snapshot. 5-min per-
    product cooldown; repeated clicks inside the window return the
    cached state so the frontend can still flash the "Up to date"
    badge without lying about a backend refresh.

    Returns:
      * 202 with {status: "refreshed", market_price_usd, low, high,
        cooldown_until}
      * 429 if the cooldown is active
      * 404 if product is missing or has no TCGplayer group id
      * 503 if TCGCSV was unreachable — caller should try again
    """
    import os as _os  # noqa: F401  (retained for parity with card refresh)
    import time as _time

    import httpx as _httpx

    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.tcgplayer_product_id is None or product.tcgplayer_group_id is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Product has no TCGplayer id / group — refresh only works "
                "for products imported from TCGCSV"
            ),
        )

    now = _time.time()
    last = _PRODUCT_REFRESH_LAST_FIRE.get(product_id, 0.0)
    if now - last < _PRODUCT_REFRESH_COOLDOWN_SECONDS:
        wait = int(_PRODUCT_REFRESH_COOLDOWN_SECONDS - (now - last))
        raise HTTPException(
            status_code=429,
            detail=f"Cooldown active — try again in {wait}s",
        )

    pid = int(product.tcgplayer_product_id)
    gid = int(product.tcgplayer_group_id)

    try:
        async with _httpx.AsyncClient(
            timeout=20.0, headers={"User-Agent": _TCGCSV_UA}
        ) as client:
            pr = await client.get(
                f"{_TCGCSV_BASE}/{_POKEMON_CATEGORY_ID}/{gid}/prices"
            )
            pr.raise_for_status()
            price_row = next(
                (r for r in pr.json().get("results", []) if r.get("productId") == pid),
                None,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"TCGCSV unreachable: {exc}",
        )

    if price_row is None:
        raise HTTPException(
            status_code=404,
            detail="TCGCSV group does not include this product",
        )

    market = price_row.get("marketPrice") or price_row.get("midPrice") or price_row.get("lowPrice")
    low = price_row.get("lowPrice")
    high = price_row.get("highPrice")

    if market is None:
        raise HTTPException(
            status_code=503,
            detail="TCGCSV returned no usable price for this product",
        )

    # Update Product row
    product.market_price_usd = float(market)
    if low is not None:
        product.low_price_usd = float(low)
    if high is not None:
        product.high_price_usd = float(high)

    # Upsert today's snapshot
    from sqlalchemy.dialects.postgresql import insert as _pg_insert
    from sqlalchemy.dialects.sqlite import insert as _sqlite_insert

    today = date.today().isoformat()
    dialect = db.bind.dialect.name
    ins_cls = _pg_insert if dialect == "postgresql" else _sqlite_insert
    stmt = ins_cls(ProductPriceSnapshot).values(
        [
            {
                "product_id": product.id,
                "source": "tcgplayer",
                "market_price_usd": float(market),
                "low_price_usd": float(low) if low is not None else None,
                "mid_price_usd": (
                    float(price_row.get("midPrice"))
                    if price_row.get("midPrice") is not None
                    else None
                ),
                "high_price_usd": float(high) if high is not None else None,
                "snapshot_date": today,
            }
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["product_id", "source", "snapshot_date"],
        set_={
            "market_price_usd": stmt.excluded.market_price_usd,
            "low_price_usd": stmt.excluded.low_price_usd,
            "mid_price_usd": stmt.excluded.mid_price_usd,
            "high_price_usd": stmt.excluded.high_price_usd,
        },
    )
    await db.execute(stmt)
    await db.commit()

    _PRODUCT_REFRESH_LAST_FIRE[product_id] = now

    return {
        "status": "refreshed",
        "product_id": product_id,
        "market_price_usd": float(market),
        "low_price_usd": float(low) if low is not None else None,
        "high_price_usd": float(high) if high is not None else None,
        "cooldown_until": int(now + _PRODUCT_REFRESH_COOLDOWN_SECONDS),
    }


@router.get("/{product_id}/live-listings", response_model=dict)
async def get_product_live_listings(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=20),
) -> dict:
    """Live eBay listings for a sealed product. Mirrors the card-side
    /cards/{id}/live-listings endpoint so the same UI component pattern
    works on both surfaces.

    Product searches don't need the strict per-card number filter —
    eBay's Browse ranking for a full product name ("Prismatic
    Evolutions Elite Trainer Box") already returns the right SKU
    reliably. We still drop below-USD and negative-price rows to keep
    the panel clean.
    """
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")

    query = f"pokemon {product.name}".strip()
    try:
        async with EbayClient() as ebay:
            result = await ebay.browse_search(query, limit=min(limit * 2, 30))
    except EbayClientError as e:
        return {"listings": [], "query": query, "error": str(e)}
    except Exception as e:
        return {"listings": [], "query": query, "error": f"unexpected: {e}"}

    raw_items = result.get("itemSummaries") or []
    listings: list[dict] = []
    for it in raw_items:
        if len(listings) >= limit:
            break
        price_obj = it.get("price") or {}
        try:
            price_v = float(price_obj.get("value", 0))
        except (TypeError, ValueError):
            continue
        if price_v <= 0:
            continue
        currency = price_obj.get("currency", "USD")
        if currency != "USD":
            continue
        ship_cost = 0.0
        ship_opts = it.get("shippingOptions") or []
        if ship_opts:
            ship_obj = ship_opts[0].get("shippingCost") or {}
            try:
                ship_cost = float(ship_obj.get("value", 0))
            except (TypeError, ValueError):
                ship_cost = 0.0
        image_url = None
        image_obj = it.get("image") or {}
        if isinstance(image_obj, dict):
            image_url = image_obj.get("imageUrl")
        listings.append(
            {
                "title": it.get("title") or "",
                "price_usd": price_v,
                "shipping_usd": ship_cost,
                "total_usd": price_v + ship_cost,
                "url": it.get("itemWebUrl") or it.get("itemHref"),
                "image_url": image_url,
                "seller": (it.get("seller") or {}).get("username"),
                "condition": it.get("condition"),
                "location": (it.get("itemLocation") or {}).get("country"),
            }
        )

    return {
        "listings": listings,
        "query": query,
        "product_id": product_id,
    }


@router.get("/set/{set_id}/list", response_model=list[ProductRead])
async def list_products_for_set(
    set_id: str,
    response: Response,
    include_unpriced: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> list[ProductRead]:
    """All sealed products for a set — used by /sets/[id] page's
    'Sealed products' section. Ordered by price desc so the big-ticket
    Booster Box / ETB Case land first. Unpriced SKUs hidden by default
    so a fresh /sets/[id] doesn't lead with `—` tiles."""
    s = await db.get(Set, set_id)
    if s is None:
        raise HTTPException(404, "Set not found")
    stmt = select(Product).where(Product.set_id == set_id)
    if not include_unpriced:
        stmt = stmt.where(Product.market_price_usd.is_not(None))
    stmt = stmt.order_by(Product.market_price_usd.desc().nullslast())
    rows = (await db.execute(stmt)).scalars().all()
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return [_row_to_read(p, s.name) for p in rows]
