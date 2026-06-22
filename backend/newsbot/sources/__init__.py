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


# Import side-effects register sources. New source modules go in this
# list (e.g. `from . import bulbanews  # noqa: F401` in Phase 2).
from . import pokebeach  # noqa: E402,F401


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
    """Run the source's enricher if it has one. No-op if the source
    didn't register one — caller falls back to title + summary."""
    enricher = ENRICHERS.get(item.source_name.lower().replace(" ", ""))
    if not enricher:
        return item
    try:
        return await enricher(item)
    except Exception as exc:
        log.exception("enrich failed for %s: %s", item.url, exc)
        return item
