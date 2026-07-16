"""Long-form editorial column source (Phase B Sprint 6).

Human-triggered deep-essay pipeline. LO fires a workflow with a
topic string; the source pulls related cards from our own catalog
AND recent context from Serper (news + web), then hands Claude a
deep-essay prompt with a 1500-2500 word target and a lore/story
voice — the piece Collectory's /reads slot for '25주년 회고'-type
posts.

Unlike Sprints 1-5 (data-driven auto sources), this source is
strictly manual — the workflow runs on workflow_dispatch only,
never on a schedule, and the topic parameter is required.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from urllib.parse import urljoin

import httpx

from ..config import settings
from . import NewsItem, register

log = logging.getLogger("newsbot.sources.editorial_column")

REQUEST_TIMEOUT = 60.0
SERPER_SEARCH_URL = "https://google.serper.dev/search"
SERPER_NEWS_URL = "https://google.serper.dev/news"

CARD_GALLERY_SIZE = 15
WEB_SNIPPETS_TARGET = 8


def _topic_slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "column"


async def _fetch_json(url: str, params: dict | None = None) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            log.warning(
                "editorial_column: %s → %d %s",
                url, r.status_code, r.text[:200],
            )
            return None
        return r.json()
    except Exception as exc:
        log.exception("editorial_column: fetch %s failed: %s", url, exc)
        return None


async def _serper_post(url: str, payload: dict) -> dict | None:
    if not settings.serper_api_key:
        return None
    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            log.warning(
                "editorial_column: serper %s → %d %s",
                url, r.status_code, r.text[:200],
            )
            return None
        return r.json()
    except Exception as exc:
        log.exception("editorial_column: serper %s failed: %s", url, exc)
        return None


@register("editorial_column")
async def crawl() -> list[NewsItem]:
    if not getattr(settings, "editorial_column_enabled", False):
        log.info(
            "editorial_column: disabled "
            "(EDITORIAL_COLUMN_ENABLED=1 to enable)"
        )
        return []

    topic = (getattr(settings, "editorial_column_topic", "") or "").strip()
    if not topic:
        log.warning(
            "editorial_column: no topic set (EDITORIAL_COLUMN_TOPIC required)"
        )
        return []

    base = settings.pulllist_api_base.rstrip("/") + "/"

    # Card gallery — search our own catalog for cards matching the
    # topic. Sort by price so the gallery leads with cards actually
    # worth talking about (bulk hits from a broad topic like
    # 'Charizard' would drown the essay in commons otherwise).
    cards_data = await _fetch_json(
        urljoin(base, "cards/search"),
        {
            "q": topic,
            "sort": "price_desc",
            "page_size": CARD_GALLERY_SIZE,
            "language": "en",
        },
    )
    cards = (cards_data or {}).get("items", []) if isinstance(cards_data, dict) else []

    # Web context — Serper /news for recent framing + /search for
    # timeless / historical / retrospective material. Both are
    # best-effort; if the API key is missing or the query blanks
    # out, the column falls back to card-only.
    news_hits: list[dict] = []
    web_hits: list[dict] = []
    news_resp = await _serper_post(SERPER_NEWS_URL, {"q": topic, "num": 8})
    if news_resp:
        news_hits = news_resp.get("news", []) or []
    web_resp = await _serper_post(
        SERPER_SEARCH_URL,
        {"q": f"Pokemon {topic} history", "num": 8},
    )
    if web_resp:
        web_hits = web_resp.get("organic", []) or []

    if not cards and not news_hits and not web_hits:
        log.warning(
            "editorial_column: no material at all for topic %r — skipping",
            topic,
        )
        return []

    today = date.today()
    slug = _topic_slug(topic)

    payload = {
        "topic": topic,
        "cards": cards,
        "news_hits": [
            {
                "title": h.get("title"),
                "snippet": h.get("snippet"),
                "link": h.get("link"),
                "source": h.get("source"),
                "date": h.get("date"),
            }
            for h in news_hits[:WEB_SNIPPETS_TARGET]
        ],
        "web_hits": [
            {
                "title": h.get("title"),
                "snippet": h.get("snippet"),
                "link": h.get("link"),
            }
            for h in web_hits[:WEB_SNIPPETS_TARGET]
        ],
    }

    inline: list[dict[str, str]] = []
    for c in cards[:10]:
        img = c.get("image_small") or c.get("image_large")
        if img:
            inline.append({
                "url": img[:512],
                "caption": (c.get("name") or "")[:120],
            })

    hero = (
        (cards[0].get("image_large") or cards[0].get("image_small"))
        if cards else None
    )

    log.info(
        "editorial_column: topic=%r cards=%d news=%d web=%d",
        topic, len(cards), len(news_hits), len(web_hits),
    )
    return [
        NewsItem(
            url=f"pulllist://editorial-column/{slug}-{today.isoformat()}",
            title=f"Editorial — {topic}",
            summary=(
                f"Long-form column on {topic} — historical context, "
                f"related cards from the PullList catalog, and current "
                f"collector angle."
            ),
            source_name="editorial_column",
            source_lang="en",
            published_at=today.isoformat(),
            raw_text=json.dumps(payload),
            hero_image_url=hero,
            inline_images=inline,
        )
    ]
