"""Illustrator feature source (Phase B Sprint 4).

Collectory-style artist feature — auto-rotating on the top illustrator
that surfaces in this month's chase-tier catalog. The two-step fetch
(top-artists → by-artist) keeps the pick data-driven: whoever
illustrated the most cards >= $100 is who gets featured this month.

An explicit override via settings.illustrator_feature_artist skips
the auto-rotation and features that name directly (useful for a
guest-editor pick or an off-cycle drop).

Dedupe: source_url = pulllist://illustrator-feature/<slug>-<yyyy-mm>
so the same artist can be re-featured in a later month if they earn
it again.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from urllib.parse import urljoin

import httpx

from ..config import settings
from . import NewsItem, register

log = logging.getLogger("newsbot.sources.illustrator_feature")

REQUEST_TIMEOUT = 60.0
TOP_CARDS = 15  # gallery size
AUTO_MIN_PRICE = 100.0  # min card price to count toward top-artists ranking
FEATURE_MIN_PRICE = 5.0  # min per-card price in the actual gallery


def _artist_slug(artist: str) -> str:
    """Lowercased, hyphenated, ASCII-only slug for the synthetic
    source_url. Matches the shape our news post slugs already take."""
    return re.sub(r"[^a-z0-9]+", "-", artist.lower()).strip("-") or "artist"


async def _fetch_json(url: str, params: dict | None = None) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            log.warning(
                "illustrator_feature: %s → %d %s",
                url, r.status_code, r.text[:200],
            )
            return None
        return r.json()
    except Exception as exc:
        log.exception("illustrator_feature: fetch %s failed: %s", url, exc)
        return None


@register("illustrator_feature")
async def crawl() -> list[NewsItem]:
    if not getattr(settings, "illustrator_feature_enabled", False):
        log.info(
            "illustrator_feature: disabled "
            "(ILLUSTRATOR_FEATURE_ENABLED=1 to enable)"
        )
        return []

    base = settings.pulllist_api_base.rstrip("/") + "/"

    # Auto vs. override pick.
    override = getattr(settings, "illustrator_feature_artist", "") or ""
    if override:
        artist = override.strip()
        log.info("illustrator_feature: override artist=%r", artist)
    else:
        top_artists = await _fetch_json(
            urljoin(base, "cards/top-artists"),
            {"min_usd": AUTO_MIN_PRICE, "limit": 10, "language": "en"},
        )
        artists = (top_artists or {}).get("artists", [])
        if not artists:
            log.warning("illustrator_feature: /cards/top-artists returned no rows")
            return []
        artist = artists[0]["artist"]
        log.info(
            "illustrator_feature: auto-picked %r (%d cards >= $%s)",
            artist, artists[0].get("card_count"), AUTO_MIN_PRICE,
        )

    # Pull the gallery.
    gallery = await _fetch_json(
        urljoin(base, "cards/by-artist"),
        {
            "artist": artist,
            "limit": TOP_CARDS,
            "language": "en",
            "sort": "price_desc",
        },
    )
    items_data = (gallery or {}).get("items", []) or []
    # Filter to cards above the feature floor — an artist with 3 chase
    # cards and 12 bulk shouldn't render as a 15-card gallery of bulk.
    items_data = [
        c for c in items_data
        if (c.get("market_price_usd") or 0) >= FEATURE_MIN_PRICE
    ]
    if not items_data:
        log.warning(
            "illustrator_feature: no cards above $%s for artist %r",
            FEATURE_MIN_PRICE, artist,
        )
        return []

    today = date.today()
    month_id = today.strftime("%Y-%m")
    slug = _artist_slug(artist)

    payload = {
        "month_id": month_id,
        "artist": artist,
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

    return [
        NewsItem(
            url=f"pulllist://illustrator-feature/{slug}-{month_id}",
            title=f"Artist Feature — {artist}",
            summary=(
                f"Top {len(items_data)} cards credited to {artist} on the "
                f"PullList catalog for {month_id}."
            ),
            source_name="illustrator_feature",
            source_lang="en",
            published_at=today.isoformat(),
            raw_text=json.dumps(payload),
            hero_image_url=hero,
            inline_images=inline,
        )
    ]
