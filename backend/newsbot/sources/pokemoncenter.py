"""Pokemon Center per-host enricher.

The generic enricher 403s on pokemoncenter.com — their Cloudflare
Bot Management blocks both curl_cffi (TLS fingerprint) and Scrapling
Stealth (browser fingerprint detection even on a real headless
Chromium). Without a residential proxy budget this site is
effectively un-scrapeable.

Workaround: skip the page fetch entirely. Use Serper's `/images`
endpoint as a side-channel to find the product image — Google has
already indexed Pokemon Center's image CDN (which is NOT behind the
same Bot Management as the product pages), so an image search for
the product title returns a usable, public, hot-link-friendly URL
that we can wrap through weserv.

Body content stays as the Serper /news snippet (`item.summary`) the
crawler already populated. Pokemon Center product pages are mostly
fluff prose around a single SKU + price + drop date, all of which
are already in the Serper snippet — the generator's `product/drop
page` prompt branch is built for exactly this thin-source case.

Cost: one extra Serper credit per Pokemon Center item enriched.
Daily ceiling of 5 posts × ~2 Pokemon Center hits = ~60 credits/
month on top of the 210 the /news queries spend. Still under the
2500 free tier with room.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from ..config import settings
from . import NewsItem, register_enricher

log = logging.getLogger("newsbot.sources.pokemoncenter")

SERPER_IMAGES_URL = "https://google.serper.dev/images"
SERPER_TIMEOUT = 30.0


def _looks_like_image_url(url: str) -> bool:
    """Accept only http(s) URLs. Drops the data: URIs Serper sometimes
    returns inline (same family of broken-thumbnail bug fixed for
    /news earlier — /images returns them too)."""
    return bool(url) and url.startswith(("http://", "https://"))


async def _serper_image_search(title: str) -> str | None:
    """One-shot Serper /images call for a Pokemon Center product
    title. Returns the first http(s) imageUrl, or None on any
    failure (auth, network, no results, all results data: URIs)."""
    if not settings.serper_api_key:
        log.warning(
            "pokemoncenter: SERPER_API_KEY not set, can't side-channel image"
        )
        return None
    # `site:pokemoncenter.com` narrows results to the source's own
    # image CDN — keeps stock photos / fan sites out of the way.
    query = f"site:pokemoncenter.com {title}"
    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": 5}
    try:
        async with httpx.AsyncClient(timeout=SERPER_TIMEOUT) as client:
            r = await client.post(SERPER_IMAGES_URL, headers=headers, json=payload)
        if r.status_code != 200:
            log.warning(
                "pokemoncenter: serper /images → %d for %r: %s",
                r.status_code, title[:60], r.text[:200],
            )
            return None
        data = r.json()
    except Exception as exc:
        log.warning(
            "pokemoncenter: serper /images %r failed: %s", title[:60], exc
        )
        return None
    for img in data.get("images", []) or []:
        candidate = (img.get("imageUrl") or "").strip()
        if _looks_like_image_url(candidate):
            return candidate[:512]
        # Some result rows put the URL under thumbnailUrl instead
        # — Google's image rendering quirk.
        thumb = (img.get("thumbnailUrl") or "").strip()
        if _looks_like_image_url(thumb):
            return thumb[:512]
    return None


# Pokemon Center responses sit at multiple hosts depending on the
# market — register every observed variant. Add more here if a new
# regional store surfaces in logs.
_POKEMONCENTER_HOSTS = (
    "www.pokemoncenter.com",
    "pokemoncenter.com",
)


async def _enrich(item: NewsItem) -> NewsItem:
    """Side-channel enricher — never tries to fetch the product
    page (Cloudflare always 403s us). Asks Serper /images for a
    product image, falls back to whatever hero the crawler already
    has (Serper /news imageUrl, if any, after our data: URI filter).
    Body stays the Serper snippet."""
    # Hero hierarchy: Serper /images > whatever the crawler stamped
    # (which after the data: URI fix is either a valid http URL or
    # None). Don't downgrade a known-good hero with a missing one.
    image = await _serper_image_search(item.title)
    new_hero = image or item.hero_image_url
    log.info(
        "pokemoncenter enrich: %s → side-channel hero=%s",
        urlparse(item.url).path[:80], bool(image),
    )
    return item.model_copy(update={"hero_image_url": new_hero})


# Register the same enricher under each host variant so
# enrich_item()'s lookup (source_name.lower().replace(" ", "")) hits
# regardless of which form Serper returned.
for _host in _POKEMONCENTER_HOSTS:
    register_enricher(_host)(_enrich)
