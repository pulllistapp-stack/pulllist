"""Serper-driven discovery source (Phase 2 Track A).

Instead of crawling a fixed feed, we run a configurable list of
queries through Serper's /news endpoint (Google news results), dedupe
results by URL, filter by a domain allowlist, and return them as
NewsItems. The pipeline's generic enricher (registered here for the
special `__generic__` key) then handles fetching + body/og extraction
for any host.

Provider: Serper (google.serper.dev). Free tier 2,500 credits/month
= 1 credit per /news call. At ~1-3 queries/day we use ~30-90/month,
well inside free. The /news endpoint is preferred over /search
because it returns date-stamped recent articles instead of generic
web results.

Off by default — flip `web_search_enabled=True` (env
`WEB_SEARCH_ENABLED=1`) when ready to start collecting.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

import httpx
from curl_cffi.requests import AsyncSession

from ..config import settings
from . import NewsItem, get_stealth_session, register, register_enricher

log = logging.getLogger("newsbot.sources.web_search")

# Special enricher key used as the registry fallback when no per-
# source enricher matches. enrich_item() in sources/__init__.py looks
# this up after trying the item's specific source_name.
GENERIC_KEY = "__generic__"

SERPER_NEWS_URL = "https://google.serper.dev/news"
SERPER_TIMEOUT = 30.0

# News-signal keywords — untrusted-domain results must have at least
# one of these in title or snippet to be treated as news vs. stale
# product page. Prevents 'Pokemon Center listed X' posts about a
# product that shipped 4 months ago showing up as fresh news.
# Trusted Pokemon publishers (PokeBeach, Bulbapedia, Pokemon.com news)
# bypass this — their whole site is news, so any title is fair game.
_NEWS_SIGNAL_KEYWORDS = (
    "coming soon", "preorder", "pre-order", "revealed", "reveal",
    "release", "released", "releases", "launch", "launches",
    "announce", "announced", "announcement", "confirmed", "confirms",
    "leaked", "leak", "spoiler", "drops", "dropping",
    "in stock", "restock", "back in stock", "now available",
    "now listed", "just listed", "hits shelves", "hits",
    "unveiled", "debut", "debuts", "showcase", "reveal",
    "new set", "new expansion", "coming to", "arrives",
)

# Serper /news 'date' field. Absolute like "Jul 5, 2026" or relative
# like "2 days ago" / "3 hours ago" / "1 month ago" / "2 years ago".
_STALE_DATE_RE = re.compile(
    r"\b(month|months|year|years)\s+ago\b", re.IGNORECASE
)
# Absolute-date formats we've seen in Serper /news payloads.
_ABS_DATE_FORMATS = (
    "%b %d, %Y",  # 'Jul 5, 2026'
    "%B %d, %Y",  # 'July 5, 2026'
    "%Y-%m-%d",   # ISO fallback
)
# Anything older than this counts as a stale republish / re-index —
# a Pokemon Center product page from a year ago sometimes reappears
# in /news when Google re-crawls it. 90 days keeps the door open
# for legit late-write-ups without letting last-year's ETB back in.
_STALE_DATE_DAYS = 90


def _is_stale_date(date_str: str) -> bool:
    """Best-effort 'is this news article old' gate. Handles both
    relative strings ('2 years ago') and absolute dates ('Jul 5,
    2025'). Unrecognised formats fall through as not-stale so a
    legit item never gets false-negatived."""
    if not date_str:
        return False
    if _STALE_DATE_RE.search(date_str):
        return True
    stripped = date_str.strip()
    for fmt in _ABS_DATE_FORMATS:
        try:
            parsed = datetime.strptime(stripped, fmt).date()
        except ValueError:
            continue
        return (date.today() - parsed).days > _STALE_DATE_DAYS
    return False


# Regex og:* extraction — avoids pulling an extra HTML parser dep
# for what is, mechanically, three tag lookups. Robust enough for
# meta tags on every CMS we care about.
def _og(prop: str) -> re.Pattern[str]:
    return re.compile(
        r'<meta\s+(?:property|name)=[\'"]'
        + re.escape(prop)
        + r'[\'"]\s+content=[\'"]([^\'"]+)[\'"]',
        re.IGNORECASE,
    )


_OG_IMAGE_RE = _og("og:image")
_OG_DESC_RE = _og("og:description")
# Strip noisy HTML chrome — scripts/styles, then all remaining tags.
# Collapsed whitespace is rough but Claude pulls signal out fine.
_SCRIPT_STYLE_RE = re.compile(
    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

REQUEST_TIMEOUT = 30
# 25k chars (~6k tokens) lets Claude see the whole article for big
# editorial pieces (30th Celebration set lineup type) instead of a
# truncated first-third. Sonnet 4.6's 200k window has tons of room;
# the cost delta is a few cents per article for the worst case and
# zero for short ones.
GENERIC_BODY_CAP = 25000

# Inline body image extraction — used by generic_enrich to feed the
# generator's "Reference images" list (pokebeach.py has its own,
# more site-specific extractor; this one's the catch-all for every
# other host Serper hands us). Heuristics:
#   - skip hero (already the thumbnail)
#   - skip data: URIs, tiny layout chrome (icons/logos/spacers)
#   - skip width/height-attr tiny images (icons declared <200px)
#   - relative src -> absolute via urljoin
#   - cap at MAX_INLINE_IMAGES so the generator prompt stays small
MAX_INLINE_IMAGES = 20
MIN_INLINE_DIM = 200  # px — anything smaller is layout chrome

_IMG_TAG_RE = re.compile(r"<img\b([^>]+)>", re.IGNORECASE | re.DOTALL)
_ATTR_RE = re.compile(r"""(\w[\w-]*)\s*=\s*(['"])(.*?)\2""", re.DOTALL)
_BAD_PATH_RE = re.compile(
    r"(logo|icon|avatar|sprite|placeholder|spacer|tracking|pixel|emoji|badge|favicon)",
    re.IGNORECASE,
)

# WordPress + most CMS media libraries generate auto-resized
# thumbnails as `<basename>-<W>x<H>.<ext>`. The bare path
# `<basename>.<ext>` is always the original at full resolution.
# Article body <img> tags usually carry the thumbnail variant so the
# page loads fast; we want the full-res for our post since readers
# expect to see the card / product at viewable quality.
_WP_THUMB_SUFFIX_RE = re.compile(
    r"-\d+x\d+(\.(?:jpe?g|png|gif|webp|avif))(?=$|\?)",
    re.IGNORECASE,
)


def _strip_wp_thumb_suffix(url: str) -> str:
    """`/foo-300x200.jpg` → `/foo.jpg`. The size suffix pattern is
    specific enough that false positives are rare; safe to apply
    unconditionally."""
    return _WP_THUMB_SUFFIX_RE.sub(r"\1", url)


def _parse_img_attrs(tag_inner: str) -> dict[str, str]:
    return {
        m.group(1).lower(): m.group(3) for m in _ATTR_RE.finditer(tag_inner)
    }


def _extract_inline_images(
    html: str, base_url: str, hero_url: str | None
) -> list[dict[str, str]]:
    """Pull up to MAX_INLINE_IMAGES body images from generic HTML.
    Returns the same {url, caption} shape pokebeach.py produces so
    the generator + main.py inline-image proxy stay source-agnostic."""
    hero_path = (hero_url or "").split("?")[0]
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for m in _IMG_TAG_RE.finditer(html):
        if len(out) >= MAX_INLINE_IMAGES:
            break
        attrs = _parse_img_attrs(m.group(1))
        src = attrs.get("src") or attrs.get("data-src")
        if not src or src.startswith("data:"):
            continue
        try:
            abs_url = urljoin(base_url, src)
        except Exception:
            continue
        if not abs_url.startswith("http"):
            continue
        # Flip WP-thumbnail URLs to their full-resolution originals
        # BEFORE the dedupe + size + hero comparisons so we don't
        # accidentally collect both a -300x200 and a full-size copy.
        abs_url = _strip_wp_thumb_suffix(abs_url)
        # Compare path-only so a query-string-resized hero (?w=800)
        # still matches its origin URL we already stored as the hero.
        if hero_path and abs_url.split("?")[0] == hero_path:
            continue
        if abs_url in seen:
            continue
        if _BAD_PATH_RE.search(urlparse(abs_url).path.lower()):
            continue
        try:
            w = int(attrs.get("width", "0") or 0)
            h = int(attrs.get("height", "0") or 0)
        except ValueError:
            w = h = 0
        # Both dimensions known AND both small → layout chrome. If
        # the attributes are missing (common — CSS sizes the image)
        # we give the image the benefit of the doubt and keep it.
        if 0 < w < MIN_INLINE_DIM and 0 < h < MIN_INLINE_DIM:
            continue
        caption = (attrs.get("alt") or "").strip()[:120]
        out.append({"url": abs_url[:512], "caption": caption})
        seen.add(abs_url)
    return out


def _domain_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _serper_tbs(days_back: int) -> str:
    """Map our days_back setting to Serper's `tbs` (time filter) param.
    Google search uses qdr:d/w/m/y for day/week/month/year buckets —
    pick the smallest bucket that contains the requested window."""
    if days_back <= 1:
        return "qdr:d"
    if days_back <= 7:
        return "qdr:w"
    if days_back <= 31:
        return "qdr:m"
    return "qdr:y"


def _build_query_with_sites(query: str, allowed_domains: list[str]) -> str:
    """Append `site:` operators to the query so Google restricts
    results at search time — saves credits and keeps result quality
    high. 9 OR clauses comfortably fits Google's operator budget."""
    if not allowed_domains:
        return query
    sites = " OR ".join(f"site:{d}" for d in allowed_domains)
    return f"{query} ({sites})"


@register("web_search")
async def crawl() -> list[NewsItem]:
    if not settings.web_search_enabled:
        log.info("web_search: disabled (WEB_SEARCH_ENABLED=1 to enable)")
        return []
    if not settings.serper_api_key:
        log.warning("web_search: SERPER_API_KEY not set — skipping")
        return []
    if not settings.web_search_queries:
        log.warning("web_search: no queries configured — skipping")
        return []

    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    tbs = _serper_tbs(settings.web_search_days_back)
    items: list[NewsItem] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(timeout=SERPER_TIMEOUT) as client:
        for query in settings.web_search_queries:
            q = _build_query_with_sites(query, settings.web_search_allowed_domains)
            payload = {
                "q": q,
                "num": settings.web_search_max_per_query,
                "tbs": tbs,
            }
            try:
                r = await client.post(
                    SERPER_NEWS_URL, headers=headers, json=payload
                )
                if r.status_code != 200:
                    log.warning(
                        "web_search: serper /news → %d for %r: %s",
                        r.status_code, query, r.text[:200],
                    )
                    continue
                data = r.json()
            except Exception as exc:
                log.exception("web_search: serper query %r failed: %s", query, exc)
                continue
            results = data.get("news", []) or []
            log.info("web_search: query %r → %d results", query, len(results))
            required_kws = [
                k.lower() for k in (settings.web_search_required_keywords or [])
            ]
            trusted = [d.lower() for d in (settings.web_search_trusted_domains or [])]
            for hit in results:
                url = (hit.get("link") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                domain = _domain_of(url)
                # Google `site:` operator already narrows to allowed
                # domains; this is the safety net for redirects or
                # operator misses.
                if not any(d in domain for d in settings.web_search_allowed_domains):
                    log.info("web_search: skip off-allowlist %s", domain)
                    continue
                title = (hit.get("title") or "").strip()
                snippet = (hit.get("snippet") or "").strip()
                if not title:
                    continue
                # Freshness gate — Serper /news occasionally returns
                # old product pages that Google re-crawled. Skip
                # relative dates >= 1 month ago AND absolute dates
                # older than _STALE_DATE_DAYS. Unknown date formats
                # fall through (better a legit article than an old
                # ETB false-negative).
                date_str = (hit.get("date") or "").strip()
                if _is_stale_date(date_str):
                    log.info(
                        "web_search: skip stale %r (date=%r)",
                        title[:80], date_str,
                    )
                    continue
                # Topic gate — Pokemon-only publisher domains bypass
                # the keyword filter (set names + character names are
                # already topical). Generic retailers (Target, BestBuy,
                # TCGPlayer) need a Pokemon keyword in title/snippet
                # to slip past the Flesh-and-Blood / Magic / MLB /
                # Yu-Gi-Oh / D&D noise we saw in earlier dry-runs.
                is_trusted = any(t in domain for t in trusted)
                if not is_trusted and required_kws:
                    haystack = (title + " " + snippet).lower()
                    if not any(kw in haystack for kw in required_kws):
                        log.info(
                            "web_search: skip off-topic %r (untrusted domain + no keyword)",
                            title[:80],
                        )
                        continue
                # News-signal gate — untrusted domains (retailers)
                # also need at least one news-verb ("revealed",
                # "preorder", "launches", etc.) in title+snippet.
                # A raw product page URL that Google surfaces as
                # "news" without any news framing is almost always
                # a restock / re-index of an old product — skipping
                # here saves the Claude call.
                if not is_trusted:
                    haystack = (title + " " + snippet).lower()
                    if not any(kw in haystack for kw in _NEWS_SIGNAL_KEYWORDS):
                        log.info(
                            "web_search: skip no-news-signal %r",
                            title[:80],
                        )
                        continue
                # Serper /news bonus: imageUrl + publisher source for
                # nicer thumbnail fallback. The generic enricher will
                # override hero_image_url with the page's og:image
                # later — this seeds it in case the page has no og.
                #
                # Discard: data: URIs (Serper sometimes returns the
                # base64-encoded thumbnail inline instead of a URL —
                # weserv can't proxy those, the post then renders as
                # a broken image), non-http(s) schemes, and anything
                # not URL-shaped. The enricher will fill the real
                # og:image later if there is one.
                raw_image = (hit.get("imageUrl") or "").strip()
                if raw_image.startswith(("http://", "https://")):
                    image_url = raw_image
                else:
                    if raw_image:
                        log.info(
                            "web_search: discard non-http imageUrl for %r (got %s...)",
                            title[:60], raw_image[:30],
                        )
                    image_url = ""
                items.append(
                    NewsItem(
                        url=url[:512],
                        title=title[:512],
                        summary=snippet[:480],
                        source_name=domain or "web",
                        source_lang="en",
                        hero_image_url=image_url[:512] or None,
                    )
                )
    log.info(
        "web_search: %d unique items across %d queries",
        len(items),
        len(settings.web_search_queries),
    )
    return items


async def _fetch_html(url: str) -> str | None:
    """Two-tier fetch: try curl_cffi (Chrome JA3 — fast, no JS) first.
    On 403 or any error, fall back to the shared Scrapling Stealth
    session (real Chromium with solve_cloudflare=True) which defeats
    the JS interstitial Pokemon Center and similar retailers serve to
    unknown clients. Returns the raw HTML string or None if both
    tiers fail."""
    async with AsyncSession(impersonate="chrome120", timeout=REQUEST_TIMEOUT) as s:
        try:
            r = await s.get(url, allow_redirects=True)
            if r.status_code == 200:
                return r.text
            log.info(
                "generic_enrich: curl_cffi %s → %d, trying stealth fallback",
                url, r.status_code,
            )
        except Exception as exc:
            log.warning(
                "generic_enrich: curl_cffi %s failed (%s), trying stealth",
                url, exc,
            )

    try:
        session = await get_stealth_session()
        page = await session.fetch(url, google_search=False)
        status = getattr(page, "status", None)
        if status is not None and status != 200:
            log.warning("generic_enrich: stealth %s → %d", url, status)
            return None
        # Scrapling Adaptor exposes the raw response body via .body
        # (bytes) — decoded to str preserves the og:* meta tags for
        # our regex extraction. Falls back to str(page) on attribute
        # mismatch across versions.
        body = getattr(page, "body", None)
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        if isinstance(body, str):
            return body
        # Last resort — Adaptor's repr/str is the HTML in most builds.
        return str(page)
    except Exception as exc:
        log.warning("generic_enrich: stealth %s failed: %s", url, exc)
        return None


@register_enricher(GENERIC_KEY)
async def generic_enrich(item: NewsItem) -> NewsItem:
    """Generic fetch + og:* + plaintext body extraction. Used as the
    registry fallback for any source_name without a per-domain
    enricher. Tiered fetch (curl_cffi → Stealth) handles both light-
    weight pages and Cloudflare-walled retailer product pages."""
    html_text = await _fetch_html(item.url)
    if not html_text:
        return item
    hero_m = _OG_IMAGE_RE.search(html_text)
    desc_m = _OG_DESC_RE.search(html_text)
    hero = (
        _strip_wp_thumb_suffix(hero_m.group(1).strip())[:512]
        if hero_m else item.hero_image_url
    )
    desc = (
        desc_m.group(1).strip()[:480] if desc_m else item.summary
    )
    inline_images = _extract_inline_images(html_text, item.url, hero)
    body = _SCRIPT_STYLE_RE.sub(" ", html_text)
    body = _TAG_RE.sub(" ", body)
    body = _WS_RE.sub(" ", body).strip()[:GENERIC_BODY_CAP]
    log.info(
        "generic_enrich: %s → hero=%s body=%d inline=%d",
        urlparse(item.url).hostname,
        bool(hero),
        len(body),
        len(inline_images),
    )
    return item.model_copy(
        update={
            "raw_text": body,
            "hero_image_url": hero,
            "summary": desc,
            "inline_images": inline_images,
        }
    )
