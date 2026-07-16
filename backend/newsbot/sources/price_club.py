"""Monthly '$1000+ club' price ranking (Phase B Sprint 3).

Emits one Collectory-style ranking post per fire — the top 20 EN
cards priced at or above the configured floor. Aimed at the
monthly cadence: catalog turnover is slow enough that a weekly
version would mostly reshuffle the same 20 cards.

Dedupe: source_url = pulllist://price-club/{yyyy-mm}. One post per
calendar month.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from urllib.parse import urljoin

import httpx

from ..config import settings
from . import NewsItem, register

log = logging.getLogger("newsbot.sources.price_club")

REQUEST_TIMEOUT = 60.0
# Monthly rotation — cycles through 4 angles so the same top 20
# vintage cards don't get republished every month. month % 4:
#   0 → $1000 floor, top 20 overall (default 'club')
#   1 → $500 floor, top 20 modern (era≥2020)     ← mid-tier / recent
#   2 → $2000 floor, top 20                       ← ultra-elite tier
#   3 → $250 floor, top 20 modern                 ← accessible tier
# Every rotation still uses the same /cards/top-priced endpoint;
# only the params (and post title) shift. LO can override with
# PRICE_CLUB_MIN_USD if a specific fire wants a specific band.
_ROTATIONS = [
    {"min_usd": 1000.0, "label": "$1000+ Club",  "focus": None},
    {"min_usd": 500.0,  "label": "$500+ Club",   "focus": "modern"},
    {"min_usd": 2000.0, "label": "$2000+ Club",  "focus": None},
    {"min_usd": 250.0,  "label": "$250+ Club",   "focus": "modern"},
]
TOP_N = 20


@register("price_club")
async def crawl() -> list[NewsItem]:
    if not getattr(settings, "price_club_enabled", False):
        log.info("price_club: disabled (PRICE_CLUB_ENABLED=1 to enable)")
        return []

    today = date.today()
    override_min = getattr(settings, "price_club_min_usd", 0.0) or 0.0
    if override_min > 0:
        rotation = {
            "min_usd": override_min,
            "label": f"${int(override_min)}+ Club",
            "focus": None,
        }
    else:
        rotation = _ROTATIONS[today.month % len(_ROTATIONS)]

    base = settings.pulllist_api_base.rstrip("/") + "/"
    url = urljoin(base, "cards/top-priced")
    params = {
        "min_usd": rotation["min_usd"],
        "limit": TOP_N,
        "language": "en",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            log.warning(
                "price_club: /cards/top-priced → %d %s",
                r.status_code, r.text[:200],
            )
            return []
        data = r.json()
    except Exception as exc:
        log.exception("price_club: fetch failed: %s", exc)
        return []

    items_data = data.get("items", []) or []
    if not items_data:
        log.warning("price_club: 0 cards above $%s — nothing to publish", PRICE_FLOOR_USD)
        return []

    today = date.today()
    month_id = today.strftime("%Y-%m")

    payload = {
        "month_id": month_id,
        "min_usd": rotation["min_usd"],
        "label": rotation["label"],
        "focus": rotation["focus"],
        "limit": TOP_N,
        "count": len(items_data),
        "items": items_data,
    }

    inline: list[dict[str, str]] = []
    for c in items_data[:10]:
        img = c.get("image_small") or c.get("image_large")
        if img:
            inline.append({
                "url": img[:512],
                "caption": (c.get("name") or "")[:120],
            })

    hero = items_data[0].get("image_large") or items_data[0].get("image_small")

    log.info(
        "price_club: month=%s cards=%d label=%s (floor=$%s)",
        month_id, len(items_data), rotation["label"], rotation["min_usd"],
    )
    # Slug rotates too so cross-month URLs stay unique even when the
    # $1000 label repeats across years.
    slug_suffix = str(int(rotation["min_usd"]))
    return [
        NewsItem(
            url=f"pulllist://price-club/{month_id}-{slug_suffix}",
            title=f"{rotation['label']} — {month_id}",
            summary=(
                f"Top {len(items_data)} cards priced at or above "
                f"${rotation['min_usd']:.0f} on the PullList catalog for "
                f"{month_id}."
            ),
            source_name="price_club",
            source_lang="en",
            published_at=today.isoformat(),
            raw_text=json.dumps(payload),
            hero_image_url=hero,
            inline_images=inline,
        )
    ]
