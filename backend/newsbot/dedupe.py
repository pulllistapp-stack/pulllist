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


async def fetch_seen(
    api_base: str, token: str
) -> tuple[set[str], list[set[str]]]:
    """Return (seen_urls, seen_title_token_sets) for the newsbot to
    dedupe against.

    seen_urls: union of /news/posts/source-urls (current post rows
      with a source_url) + /news/posts/processed-urls (persistent log
      of every URL the bot has touched). Second set survives admin
      post deletion.

    seen_title_token_sets: for every processed_urls row with a
      non-empty title_tokens field, the space-split token set. The
      newsbot uses these for cross-run title-similarity dedupe —
      same story from a second source on a later day matches via
      Jaccard >= 0.6 and gets skipped before Claude is called.

    Graceful degradation for older backends: /processed-urls 404 =
      URL dedupe falls back to source-urls only, title dedupe
      returns empty."""
    seen_urls: set[str] = set()
    title_token_sets: list[set[str]] = []
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        source = await client.get(
            f"{api_base}/news/posts/source-urls",
            headers={"Authorization": f"Bearer {token}"},
        )
        source.raise_for_status()
        seen_urls |= set(source.json().keys())

        try:
            processed = await client.get(
                f"{api_base}/news/posts/processed-urls",
                headers={"Authorization": f"Bearer {token}"},
            )
            if processed.status_code == 200:
                payload = processed.json()
                for url, meta in payload.items():
                    seen_urls.add(url)
                    # Older /processed-urls responses returned a bare
                    # string per URL (outcome). Tolerate that shape
                    # so a rolling backend deploy doesn't break the
                    # bot mid-cron.
                    if isinstance(meta, dict):
                        tokens = (meta.get("title_tokens") or "").strip()
                        if tokens:
                            title_token_sets.append(set(tokens.split()))
            elif processed.status_code != 404:
                processed.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("processed-urls fetch failed (degrading): %s", exc)
    return seen_urls, title_token_sets


async def filter_unseen(
    items: list[NewsItem], api_base: str, token: str
) -> tuple[list[NewsItem], list[set[str]]]:
    """Wraps fetch_seen for the crawl pipeline. Returns fresh items
    (URL-deduped) alongside the historical title token sets, so
    _select_for_publishing can also skip cross-run title dupes."""
    seen, title_tokens = await fetch_seen(api_base, token)
    fresh = [i for i in items if i.url not in seen]
    log.info(
        "dedupe: %d incoming, %d already seen, %d fresh (%d historical titles)",
        len(items),
        len(items) - len(fresh),
        len(fresh),
        len(title_tokens),
    )
    return fresh, title_tokens


async def mark_processed(
    api_base: str, token: str, source_url: str, outcome: str,
    title_tokens: str = "",
) -> None:
    """Append the URL to the persistent dedupe log. Best-effort —
    a failure here is logged but doesn't fail the parent run (the
    bot already did the expensive work; a missed log entry just
    means the URL may be retried next run, which the verify gate
    will still cheap-skip).

    title_tokens: space-separated normalized content words for the
    item's title. Populates the field the /processed-urls GET later
    returns for cross-run title dedupe. Empty string when the caller
    doesn't have (or want) title context."""
    if not source_url:
        return
    payload: dict = {"source_url": source_url, "outcome": outcome}
    if title_tokens:
        payload["title_tokens"] = title_tokens
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(
                f"{api_base}/news/posts/processed-urls",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
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
