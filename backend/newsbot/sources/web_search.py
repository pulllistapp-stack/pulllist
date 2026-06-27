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
from urllib.parse import urlparse

import httpx
from curl_cffi.requests import AsyncSession

from ..config import settings
from . import NewsItem, register, register_enricher

log = logging.getLogger("newsbot.sources.web_search")

# Special enricher key used as the registry fallback when no per-
# source enricher matches. enrich_item() in sources/__init__.py looks
# this up after trying the item's specific source_name.
GENERIC_KEY = "__generic__"

SERPER_NEWS_URL = "https://google.serper.dev/news"
SERPER_TIMEOUT = 30.0


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
GENERIC_BODY_CAP = 8000  # chars of plain text — caps Claude input cost


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
                # Serper /news bonus: imageUrl + publisher source for
                # nicer thumbnail fallback. The generic enricher will
                # override hero_image_url with the page's og:image
                # later — this seeds it in case the page has no og.
                image_url = (hit.get("imageUrl") or "").strip()
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


@register_enricher(GENERIC_KEY)
async def generic_enrich(item: NewsItem) -> NewsItem:
    """Generic fetch + og:* + plaintext body extraction. Used as the
    registry fallback for any source_name without a per-domain
    enricher. Curl_cffi (Chrome JA3) handles most lightly-protected
    pages; pages behind a JS challenge fall back to whatever the
    search result already provided (title + snippet)."""
    async with AsyncSession(impersonate="chrome120", timeout=REQUEST_TIMEOUT) as s:
        try:
            r = await s.get(item.url, allow_redirects=True)
        except Exception as exc:
            log.warning("generic_enrich: fetch %s failed: %s", item.url, exc)
            return item
    if r.status_code != 200:
        log.warning("generic_enrich: %s → %d", item.url, r.status_code)
        return item
    html_text = r.text
    hero_m = _OG_IMAGE_RE.search(html_text)
    desc_m = _OG_DESC_RE.search(html_text)
    hero = hero_m.group(1).strip()[:512] if hero_m else item.hero_image_url
    desc = (
        desc_m.group(1).strip()[:480] if desc_m else item.summary
    )
    body = _SCRIPT_STYLE_RE.sub(" ", html_text)
    body = _TAG_RE.sub(" ", body)
    body = _WS_RE.sub(" ", body).strip()[:GENERIC_BODY_CAP]
    return item.model_copy(
        update={
            "raw_text": body,
            "hero_image_url": hero,
            "summary": desc,
        }
    )
