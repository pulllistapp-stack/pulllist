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
    """Union of two sources:

    1. /news/posts/source-urls — published + draft posts that have a
       source_url. Volatile: shrinks when LO deletes a draft.

    2. /news/posts/processed-urls — persistent log of every URL the
       bot has touched, including ones rejected at pre-flight verify
       (no thumbnail, etc) and ones whose resulting post LO later
       deleted. This is what prevents the broken-thumbnail cost
       cycle: a URL that failed verify yesterday won't get a Claude
       call today even though no post exists for it.

    A missing /processed-urls endpoint (older backend) degrades
    gracefully to source-urls only."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        source = await client.get(
            f"{api_base}/news/posts/source-urls",
            headers={"Authorization": f"Bearer {token}"},
        )
        source.raise_for_status()
        seen = set(source.json().keys())

        try:
            processed = await client.get(
                f"{api_base}/news/posts/processed-urls",
                headers={"Authorization": f"Bearer {token}"},
            )
            if processed.status_code == 200:
                seen |= set(processed.json().keys())
            elif processed.status_code != 404:
                processed.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("processed-urls fetch failed (degrading): %s", exc)
        return seen


async def mark_processed(
    api_base: str, token: str, source_url: str, outcome: str
) -> None:
    """Append the URL to the persistent dedupe log. Best-effort —
    a failure here is logged but doesn't fail the parent run (the
    bot already did the expensive work; a missed log entry just
    means the URL may be retried next run, which the verify gate
    will still cheap-skip)."""
    if not source_url:
        return
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(
                f"{api_base}/news/posts/processed-urls",
                headers={"Authorization": f"Bearer {token}"},
                json={"source_url": source_url, "outcome": outcome},
            )
        if r.status_code not in (204, 200):
            log.warning(
                "mark_processed %s → %d %s",
                source_url[:80], r.status_code, r.text[:200],
            )
    except Exception as exc:
        log.warning("mark_processed %s failed: %s", source_url[:80], exc)


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
