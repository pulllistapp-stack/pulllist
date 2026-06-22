"""PokeBeach source — scrapes the WordPress homepage.

Why not RSS? The on-site /feed endpoint is 500 upstream and /news/feed
404s — those are PokeBeach bugs we can't fix. The homepage HTML
renders fine and uses standard WP `article.post` markup.

Why curl_cffi? PokeBeach sits behind Cloudflare which JA3-fingerprints
plain httpx and returns 403. curl_cffi impersonates Chrome's TLS
fingerprint and gets through without needing a real browser.

Two-stage fetch:
  1. crawl()  → homepage HTML → 16 NewsItems (url + title only)
  2. enrich() → per-item article-page fetch → fills raw_text

main.py only calls enrich() for items that survive dedupe + the daily
limit, so a typical run hits PokeBeach 1 + daily_post_limit times
(3 total at the default limit of 2).
"""
from __future__ import annotations

import logging

from curl_cffi.requests import AsyncSession
from selectolax.parser import HTMLParser

from . import NewsItem, register, register_enricher

log = logging.getLogger("newsbot.sources.pokebeach")

INDEX_URL = "https://www.pokebeach.com/"
IMPERSONATE = "chrome120"
REQUEST_TIMEOUT = 30
MAX_ITEMS = 16  # one homepage = 16 articles; matches WP's default page size

# CSS selectors — pinned to current PokeBeach markup as of 2026-06.
# If PokeBeach restructures, the source layer is the only thing that
# needs to change. See README for the canary CSS query to re-derive.
SEL_CARD = "article.post"
SEL_CARD_TITLE = "h2.entry-title a"
SEL_CARD_EXCERPT = ".entry-content, .entry-summary"
SEL_BODY = "div.entry-content, div.post-content, article div.entry"


async def _fetch(url: str) -> str:
    async with AsyncSession(impersonate=IMPERSONATE, timeout=REQUEST_TIMEOUT) as s:
        r = await s.get(url, allow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(
                f"pokebeach fetch {url} → {r.status_code}"
            )
        return r.text


@register("pokebeach")
async def crawl() -> list[NewsItem]:
    html = await _fetch(INDEX_URL)
    tree = HTMLParser(html)
    cards = tree.css(SEL_CARD)
    log.info("pokebeach index: %d article cards on homepage", len(cards))

    items: list[NewsItem] = []
    for card in cards[:MAX_ITEMS]:
        link = card.css_first(SEL_CARD_TITLE)
        if not link:
            continue
        url = (link.attributes.get("href") or "").strip()
        title = link.text(strip=True)
        if not url or not title:
            continue
        excerpt_el = card.css_first(SEL_CARD_EXCERPT)
        excerpt = excerpt_el.text(strip=True)[:480] if excerpt_el else ""
        items.append(
            NewsItem(
                url=url[:512],
                title=title[:512],
                summary=excerpt,
                source_name="PokeBeach",
                source_lang="en",
            )
        )
    return items


@register_enricher("pokebeach")
async def enrich(item: NewsItem) -> NewsItem:
    """Fetch the article page and pull the body text. Returns a new
    NewsItem with raw_text populated; leaves the original untouched on
    failure so the generator can still fall back to title + summary."""
    html = await _fetch(item.url)
    tree = HTMLParser(html)
    body_el = tree.css_first(SEL_BODY)
    if not body_el:
        log.warning("pokebeach enrich: no body element at %s", item.url)
        return item
    body = body_el.text(strip=False).strip()
    return item.model_copy(update={"raw_text": body})
