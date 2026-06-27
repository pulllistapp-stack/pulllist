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

# Body images — PokeBeach uses TWO patterns simultaneously:
#   1. <figure class="gallery-item"> for product / deck-package shots,
#      with a.js-lbImage[href] pointing at the full-size original
#      (200x113 suffix on the inner img). Optional figcaption.
#   2. Bare <img> tags (no figure wrapper) for individual card shots
#      — these litter the body of any "set reveal" article (10-20+
#      cards per article).
# Two-pass strategy avoids walking parents (Scrapling's Selector
# doesn't expose .parent / .tag — and even the attribute API differs
# from selectolax's): first collect every figure's lightbox URL +
# caption; then collect every bare img's stripped src. Dedupe at the
# end by full-size URL — the bare-img path produces the same URL as
# the figure path once -WxH is stripped, so figure-wrapped images
# naturally win (richer caption) and the bare second-pass entry
# drops out.
SEL_FIGURE = "figure"
SEL_FIG_FULL_URL = "a.js-lbImage::attr(href)"
SEL_FIG_CAPTION = "figcaption"
SEL_BODY_IMG_SRC = "img::attr(src), img::attr(data-src)"
MAX_INLINE_IMAGES = 10  # cap so prompts + articles don't bloat
# WP appends -WxH before the extension on resized thumbnails. Strip
# to get the full-size original.
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
        # Also block the post-WP-suffix-strip form of the hero so a
        # bare-img with the thumbnail URL doesn't slip in as "new".
        seen.add(_WP_THUMB_SUFFIX.sub("", hero))

    body_node = body_matches[0] if body_matches else None

    # Pass 1: figures — pick up lightbox URL + figcaption.
    if body_node is not None:
        for fig in body_node.css(SEL_FIGURE):
            if len(inline_images) >= MAX_INLINE_IMAGES:
                break
            url = (fig.css(SEL_FIG_FULL_URL).get() or "").strip()
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            cap_el = fig.css(SEL_FIG_CAPTION)
            caption = (
                cap_el[0].get_all_text(separator=" ", strip=True)[:200]
                if cap_el
                else ""
            )
            seen.add(url)
            inline_images.append({"url": url[:512], "caption": caption})

    # Pass 2: bare imgs — full-size URL via WP-suffix strip. Pseudo-
    # element CSS gets us the attribute as a string list without
    # touching the Selector's attribute API (which differs from
    # selectolax's). data-src as fallback for lazy-loaded images.
    if body_node is not None and len(inline_images) < MAX_INLINE_IMAGES:
        srcs: list[str] = []
        srcs += [s for s in body_node.css("img::attr(src)").getall() if s]
        srcs += [s for s in body_node.css("img::attr(data-src)").getall() if s]
        for raw in srcs:
            if len(inline_images) >= MAX_INLINE_IMAGES:
                break
            url = _WP_THUMB_SUFFIX.sub("", raw.strip())
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            inline_images.append({"url": url[:512], "caption": ""})

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
