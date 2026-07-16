"""eBay auction highlights source (Phase B Sprint 5).

Weekly digest of what actually traded on eBay over the last 7 days,
ranked by aggregate sales_count. Complements the Sprint 1 market-
movers report — that one covers price direction, this one covers
volume ('what people are actually buying').

Dedupe: source_url = pulllist://auction-highlights/<iso-week>. One
post per ISO week.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from urllib.parse import urljoin

import httpx

from ..config import settings
from . import NewsItem, register

log = logging.getLogger("newsbot.sources.auction_highlights")

REQUEST_TIMEOUT = 60.0
DAYS = 7
MIN_PRICE_USD = 50.0
TOP_N = 15


def _iso_week_id(today: date) -> str:
    yr, wk, _ = today.isocalendar()
    return f"{yr}-W{wk:02d}"


@register("auction_highlights")
async def crawl() -> list[NewsItem]:
    if not getattr(settings, "auction_highlights_enabled", False):
        log.info(
            "auction_highlights: disabled "
            "(AUCTION_HIGHLIGHTS_ENABLED=1 to enable)"
        )
        return []

    base = settings.pulllist_api_base.rstrip("/") + "/"
    url = urljoin(base, "cards/top-ebay-sales")
    params = {
        "days": DAYS,
        "min_price_usd": MIN_PRICE_USD,
        "limit": TOP_N,
        "language": "en",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            log.warning(
                "auction_highlights: /cards/top-ebay-sales → %d %s",
                r.status_code, r.text[:200],
            )
            return []
        data = r.json()
    except Exception as exc:
        log.exception("auction_highlights: fetch failed: %s", exc)
        return []

    items_data = data.get("items", []) or []
    if not items_data:
        log.warning(
            "auction_highlights: 0 cards above $%s over %d days — skipping",
            MIN_PRICE_USD, DAYS,
        )
        return []

    today = date.today()
    week_id = _iso_week_id(today)

    payload = {
        "week_id": week_id,
        "days": DAYS,
        "min_price_usd": MIN_PRICE_USD,
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
        "auction_highlights: week=%s cards=%d (min=$%s, days=%d)",
        week_id, len(items_data), MIN_PRICE_USD, DAYS,
    )
    return [
        NewsItem(
            url=f"pulllist://auction-highlights/{week_id}",
            title=f"eBay Auction Highlights — Week {week_id}",
            summary=(
                f"Top {len(items_data)} most-traded cards on eBay this "
                f"week, ranked by aggregate sold count over {DAYS} days "
                f"(minimum ${MIN_PRICE_USD:.0f})."
            ),
            source_name="auction_highlights",
            source_lang="en",
            published_at=today.isoformat(),
            raw_text=json.dumps(payload),
            hero_image_url=hero,
            inline_images=inline,
        )
    ]
