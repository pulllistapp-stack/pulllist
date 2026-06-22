"""PokeBeach source — scrapes the WordPress homepage.

Why not RSS? The on-site /feed endpoint is 500 upstream and /news/feed
404s — those are PokeBeach bugs we can't fix. The homepage HTML
renders fine and uses standard WP `article.post` markup.

Why Scrapling AsyncStealthySession with solve_cloudflare=True?
PokeBeach sits behind Cloudflare. Plain httpx 403s on TLS fingerprint;
curl_cffi (which impersonates Chrome's JA3) gets the homepage but
hits a JavaScript "Just a moment..." interstitial on article pages.
solve_cloudflare=True spins up a real headless Chromium just long
enough to execute the challenge script and harvest the clearance
cookie, then reuses it across every fetch in this run.

Two-stage fetch:
  1. crawl()  → homepage HTML → 16 NewsItems (url + title only)
  2. enrich() → per-item article-page fetch → fills raw_text

main.py only calls enrich() for items that survive dedupe + the daily
limit, so a typical run hits PokeBeach 1 + daily_post_limit times
(3 total at the default limit of 2). The single Scrapling session is
held open across all of them so the Cloudflare clearance cookie set
during crawl() is still valid when enrich() runs.
"""
from __future__ import annotations

import asyncio
import logging
import re

from scrapling.fetchers import AsyncStealthySession

from . import NewsItem, register, register_enricher

log = logging.getLogger("newsbot.sources.pokebeach")

INDEX_URL = "https://www.pokebeach.com/"
REQUEST_TIMEOUT = 60  # solve_cloudflare adds ~5-10s on the first hit
MAX_ITEMS = 16  # one homepage = 16 articles; matches WP's default page size
INTER_REQUEST_DELAY = 1.5  # seconds — polite spacing between article fetches

# CSS selectors — pinned to current PokeBeach markup as of 2026-06.
# If PokeBeach restructures, the source layer is the only thing that
# needs to change. See README for the canary CSS query to re-derive.
SEL_CARD = "article.post"
SEL_CARD_TITLE = "h2.entry-title a"
SEL_CARD_EXCERPT = ".entry-content, .entry-summary"
SEL_BODY = "div.entry-content, div.post-content, article div.entry"
# Hero image — try the og:image meta tag first (most reliable on WP),
# then the first descendant img inside the article body as a fallback.
SEL_OG_IMAGE = "meta[property='og:image']::attr(content)"
SEL_FIRST_BODY_IMG = "div.entry-content img::attr(src), article img::attr(src)"

# Body images — each <figure class="gallery-item"> wraps an image.
# a.js-lbImage is PokeBeach's lightbox anchor and points at the
# full-size original (200x113 etc. suffixes appear only on the inner
# <img src>). Caption sits in <figcaption>, sometimes empty.
SEL_FIGURE = "figure"
SEL_FIG_FULL_URL = "a.js-lbImage::attr(href)"
SEL_FIG_FALLBACK_SRC = "img::attr(src)"
SEL_FIG_CAPTION = "figcaption"
MAX_INLINE_IMAGES = 5  # cap so prompts + articles don't bloat
# WP appends -WxH before the extension on resized thumbnails. Strip
# to get the full-size original (used as the fallback when js-lbImage
# isn't present).
_WP_THUMB_SUFFIX = re.compile(r"-\d+x\d+(?=\.\w+$)")


# Lazy module-level session — opened on first call, reused across the
# whole bot run, leaked at process exit (one-shot script, so cleanup
# isn't worth the async-context-manager complexity).
_session: AsyncStealthySession | None = None
_session_ctx = None
_session_lock = asyncio.Lock()


async def _get_session() -> AsyncStealthySession:
    global _session, _session_ctx
    async with _session_lock:
        if _session is None:
            _session_ctx = AsyncStealthySession(
                headless=True,
                solve_cloudflare=True,
            )
            _session = await _session_ctx.__aenter__()
        return _session


async def _fetch(url: str):
    """Returns a Scrapling page object. Use .css() / .css_first() to
    extract; selectors support ::text and ::attr(name) pseudo-elements."""
    session = await _get_session()
    page = await session.fetch(url, google_search=False)
    status = getattr(page, "status", None)
    if status is not None and status != 200:
        raise RuntimeError(f"pokebeach fetch {url} → {status}")
    return page


@register("pokebeach")
async def crawl() -> list[NewsItem]:
    page = await _fetch(INDEX_URL)
    cards = page.css(SEL_CARD)
    log.info("pokebeach index: %d article cards on homepage", len(cards))

    items: list[NewsItem] = []
    for card in cards[:MAX_ITEMS]:
        # Scrapling supports parsel-style pseudo-elements; .get()
        # returns the first match's value (string), or None.
        url = card.css(f"{SEL_CARD_TITLE}::attr(href)").get()
        title = card.css(f"{SEL_CARD_TITLE}::text").get()
        if not url or not title:
            continue
        url = url.strip()
        title = title.strip()
        excerpt_matches = card.css(SEL_CARD_EXCERPT)
        excerpt = ""
        if excerpt_matches:
            # get_all_text() collects every descendant text node — what
            # we want for excerpt blocks that mix inline elements.
            excerpt = excerpt_matches[0].get_all_text(
                separator=" ", strip=True
            )[:480]
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
    """Fetch the article page; fill raw_text + hero_image_url + inline_images.

    Body, hero, and inline images are independent — a missing one
    doesn't drop the others. inline_images is capped + deduped against
    the hero so the same picture isn't sent twice.
    """
    await asyncio.sleep(INTER_REQUEST_DELAY)
    page = await _fetch(item.url)

    body = ""
    body_matches = page.css(SEL_BODY)
    if body_matches:
        body = body_matches[0].get_all_text(separator="\n", strip=True)
    else:
        log.warning("pokebeach enrich: no body element at %s", item.url)

    # og:image is the standard WordPress / Yoast hero image; falls back
    # to the first article img if the meta tag is missing. Trim to fit
    # NewsPost.thumbnail_url's 512-char column.
    hero = page.css(SEL_OG_IMAGE).get() or page.css(SEL_FIRST_BODY_IMG).get()
    hero = (hero or "").strip()[:512] or None

    inline_images: list[dict[str, str]] = []
    seen: set[str] = set()
    if hero:
        seen.add(hero)
    figures = body_matches[0].css(SEL_FIGURE) if body_matches else []
    for fig in figures:
        if len(inline_images) >= MAX_INLINE_IMAGES:
            break
        # PokeBeach lightbox anchor → full-size original; else strip the
        # -WxH WP thumbnail suffix off the inner img src.
        url = fig.css(SEL_FIG_FULL_URL).get()
        if not url:
            src = fig.css(SEL_FIG_FALLBACK_SRC).get() or ""
            url = _WP_THUMB_SUFFIX.sub("", src.strip())
        url = (url or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        cap_el = fig.css(SEL_FIG_CAPTION)
        caption = ""
        if cap_el:
            caption = cap_el[0].get_all_text(separator=" ", strip=True)[:200]
        inline_images.append({"url": url[:512], "caption": caption})
    log.info(
        "pokebeach enrich: %d body images extracted (hero=%s, body=%d chars)",
        len(inline_images), bool(hero), len(body),
    )

    return item.model_copy(
        update={
            "raw_text": body,
            "hero_image_url": hero,
            "inline_images": inline_images,
        }
    )
