"""PokeBeach RSS source.

PokeBeach exposes a standard WordPress RSS feed at /news/feed with
<title>/<link>/<description>/<pubDate>/<content:encoded> per item.
We parse it with stdlib ElementTree — no JS, no HTML quirks at this
endpoint, so Scrapling-grade selectors are overkill until Phase 2
when sources need adaptive HTML scraping.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from . import NewsItem, register

log = logging.getLogger("newsbot.sources.pokebeach")

FEED_URL = "https://www.pokebeach.com/news/feed"

# WordPress / RSS 2.0 namespace map used by content:encoded.
NS = {"content": "http://purl.org/rss/1.0/modules/content/"}

# Identify ourselves so PokeBeach can rate-limit us cleanly if needed.
USER_AGENT = (
    "PullListNewsBot/1.0 (+https://pulllist.org; "
    "contact: hi@pulllist.org)"
)

REQUEST_TIMEOUT = 30.0
MAX_ITEMS = 30


def _parse_pubdate(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        # RFC 822 (e.g. "Thu, 19 Jun 2026 14:23:00 +0000")
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(dt, datetime):
        return None
    return dt.date().isoformat()


@register("pokebeach")
async def crawl() -> list[NewsItem]:
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        r = await client.get(FEED_URL)
        r.raise_for_status()
        xml_text = r.text

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.error("pokebeach feed parse error: %s", exc)
        return []

    channel = root.find("channel")
    if channel is None:
        log.warning("pokebeach feed missing <channel>")
        return []

    items: list[NewsItem] = []
    for raw in channel.findall("item")[:MAX_ITEMS]:
        link = (raw.findtext("link") or "").strip()
        title = (raw.findtext("title") or "").strip()
        if not link or not title:
            continue
        body_el = raw.find("content:encoded", NS)
        body = (body_el.text or "").strip() if body_el is not None else ""
        summary = (raw.findtext("description") or "").strip()
        pub = _parse_pubdate(raw.findtext("pubDate"))
        items.append(
            NewsItem(
                url=link[:512],
                title=title[:512],
                summary=summary,
                raw_text=body,
                source_name="PokeBeach",
                source_lang="en",
                published_at=pub,
            )
        )
    return items
