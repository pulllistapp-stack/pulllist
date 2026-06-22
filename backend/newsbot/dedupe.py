"""Dedupe newly-crawled items against what we've already posted.

Keyed on source_url — exact match. Title-similarity dedupe (catching
the same story syndicated across PokeBeach + Bulbanews) is deferred
to Phase 2 once we have multi-source overlap to test against.
"""
from __future__ import annotations

import logging

import httpx

from .sources import NewsItem

log = logging.getLogger("newsbot.dedupe")

REQUEST_TIMEOUT = 30.0


async def fetch_seen_urls(api_base: str, token: str) -> set[str]:
    """Pull the admin {source_url: slug} map. Returns just the URL set
    — slugs aren't needed for dedupe yet."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.get(
            f"{api_base}/news/posts/source-urls",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        return set(r.json().keys())


async def filter_unseen(
    items: list[NewsItem], api_base: str, token: str
) -> list[NewsItem]:
    seen = await fetch_seen_urls(api_base, token)
    fresh = [i for i in items if i.url not in seen]
    log.info(
        "dedupe: %d incoming, %d already seen, %d fresh",
        len(items),
        len(items) - len(fresh),
        len(fresh),
    )
    return fresh
