"""Source registry. Each source module exposes `crawl()` returning a
list of NewsItem. The aggregator runs them in parallel.

Phase 1 has one source (PokeBeach). Phase 2 adds the multilingual
sweep; sources go here as additional modules + a registry entry.

Sources MAY also expose an async `enrich(item) -> NewsItem` that
fetches the full article body. The pipeline only calls enrich() for
items that survive dedupe + the daily limit, so we don't pay N
article-page fetches per run when only ~2 get published.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, Field

log = logging.getLogger("newsbot.sources")


class NewsItem(BaseModel):
    """Normalised shape every source emits. Generator + dedupe both
    key off this — keep additions backwards-compatible."""

    url: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=512)
    summary: str = ""
    source_name: str
    source_lang: str = "en"
    # YYYY-MM-DD when known. Sources that don't expose a publish date
    # leave it None and main.py stamps with today's date at publish time.
    published_at: str | None = None
    # Full article body. Empty after crawl() for sources that defer
    # body fetching to enrich(); filled in once the pipeline asks.
    raw_text: str = ""
    # Hero image extracted by enrich() — gets stamped onto the published
    # draft's thumbnail_url. Sources that don't expose images leave it
    # None and the draft renders with no image.
    hero_image_url: str | None = Field(default=None, max_length=512)
    # Body images from the source article — passed to the generator so
    # Claude can embed them inline at thematically appropriate spots.
    # Each entry: {"url": str, "caption": str}. Capped per source to
    # avoid bloating prompts or producing image-spam articles.
    inline_images: list[dict[str, str]] = Field(default_factory=list)


# Type alias for source crawler signatures.
Crawler = Callable[[], Awaitable[list[NewsItem]]]
Enricher = Callable[[NewsItem], Awaitable[NewsItem]]


# Sources register themselves here. Import-time side effect keeps the
# registry centralised without a hand-maintained list.
SOURCES: dict[str, Crawler] = {}
ENRICHERS: dict[str, Enricher] = {}


def register(name: str):
    """Decorator: @register("pokebeach") above an async crawl()."""
    def _wrap(fn: Crawler) -> Crawler:
        SOURCES[name] = fn
        return fn
    return _wrap


def register_enricher(name: str):
    """Decorator: @register_enricher("pokebeach") above an async enrich()."""
    def _wrap(fn: Enricher) -> Enricher:
        ENRICHERS[name] = fn
        return fn
    return _wrap


# Shared Scrapling Stealth session — lazily opened, reused across
# every source that needs to defeat Cloudflare JS challenges
# (PokeBeach articles, Pokemon Center product pages, etc.). Spinning
# up a real Chromium is the expensive bit (~5s); sharing one session
# across enrichers keeps that one-time per process.
_stealth_session = None  # type: ignore[var-annotated]
_stealth_session_ctx = None  # type: ignore[var-annotated]
_stealth_lock = asyncio.Lock()


async def get_stealth_session():
    """Lazy module-level singleton. Reuses the same headless Chromium
    + Cloudflare clearance cookie across every fetch in this process.
    Call close_stealth_session() before asyncio.run() returns or the
    Chromium subprocess leaks past the event loop close, producing a
    noisy 'RuntimeError: Event loop is closed' on GC."""
    global _stealth_session, _stealth_session_ctx
    async with _stealth_lock:
        if _stealth_session is None:
            from scrapling.fetchers import AsyncStealthySession  # lazy import
            _stealth_session_ctx = AsyncStealthySession(
                headless=True,
                solve_cloudflare=True,
            )
            _stealth_session = await _stealth_session_ctx.__aenter__()
        return _stealth_session


async def close_stealth_session() -> None:
    """Tear down the shared Stealth session if one was opened. Safe
    to call when no session was ever created (the lock + None-check
    make it a no-op). Swallows any close-time exceptions because
    teardown errors shouldn't poison the success of a bot run that
    has already finished publishing."""
    global _stealth_session, _stealth_session_ctx
    async with _stealth_lock:
        if _stealth_session_ctx is None:
            return
        try:
            await _stealth_session_ctx.__aexit__(None, None, None)
        except Exception as exc:
            log.warning("close_stealth_session: ignored %s", exc)
        _stealth_session = None
        _stealth_session_ctx = None


# Import side-effects register sources + their enrichers. Add new
# source modules below.
from . import pokebeach  # noqa: E402,F401
from . import web_search  # noqa: E402,F401


async def crawl_all() -> list[NewsItem]:
    """Fan out across all registered sources. A failing source is
    logged and dropped — one broken site doesn't kill the daily run."""
    async def _safe(name: str, fn: Crawler) -> list[NewsItem]:
        try:
            items = await fn()
            log.info("source %s: %d items", name, len(items))
            return items
        except Exception as exc:
            log.exception("source %s failed: %s", name, exc)
            return []

    results = await asyncio.gather(
        *(_safe(name, fn) for name, fn in SOURCES.items())
    )
    flat = [item for batch in results for item in batch]
    log.info("crawl_all: %d items across %d sources", len(flat), len(SOURCES))
    return flat


async def enrich_item(item: NewsItem) -> NewsItem:
    """Run the source's enricher. Per-source enricher wins; if none
    registered for this item's source_name, fall back to the special
    `__generic__` enricher (web_search registers it) — that handles
    any URL via plain fetch + og:* extraction. No-op if neither path
    is registered (caller falls back to title + summary)."""
    key = item.source_name.lower().replace(" ", "")
    enricher = ENRICHERS.get(key) or ENRICHERS.get("__generic__")
    if not enricher:
        return item
    try:
        return await enricher(item)
    except Exception as exc:
        log.exception("enrich failed for %s: %s", item.url, exc)
        return item
