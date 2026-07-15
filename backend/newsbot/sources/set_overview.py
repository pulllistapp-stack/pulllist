"""New-set overview report source (Phase B Sprint 2).

Detects sets that shipped in the last N days and emits one
Collectory-style overview post per set — release info + top 10
cards by market price, each linked to /cards/{card_id}. Runs off
a daily cron; if nothing new, the source returns 0 items and the
bot exits cleanly.

Dedupe: source_url is pulllist://set-overview/{set_id}, so
processed_urls blocks any re-publish of the same set even after
LO deletes the draft.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from urllib.parse import urljoin

import httpx

from ..config import settings
from . import NewsItem, register

log = logging.getLogger("newsbot.sources.set_overview")

REQUEST_TIMEOUT = 60.0

# Set-overview tuning
NEW_SET_WINDOW_DAYS = 14  # emit an overview for any set that shipped in this window
TOP_CARDS_PER_SET = 12  # how many cards to feature in the post
MAX_SETS_PER_RUN = 3  # cap so a JP-catalog backfill day can't dump 30 posts


async def _fetch_json(url: str, params: dict | None = None) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            log.warning("set_overview: %s → %d %s", url, r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception as exc:
        log.exception("set_overview: fetch %s failed: %s", url, exc)
        return None


@register("set_overview")
async def crawl() -> list[NewsItem]:
    """Return one NewsItem per recently-released set (up to MAX_SETS_PER_RUN).
    Off unless settings.set_overview_enabled — daily cron flips it on."""
    if not getattr(settings, "set_overview_enabled", False):
        log.info("set_overview: disabled (SET_OVERVIEW_ENABLED=1 to enable)")
        return []

    base = settings.pulllist_api_base.rstrip("/") + "/"

    # Pull the English catalog only for now — JP set overviews would
    # need a different prompt voice and audience decision (postponed).
    all_sets = await _fetch_json(urljoin(base, "sets"), {"language": "en"})
    if not all_sets:
        log.warning("set_overview: /sets returned nothing")
        return []

    today = date.today()
    cutoff = today - timedelta(days=NEW_SET_WINDOW_DAYS)
    fresh_sets: list[dict] = []
    for s in all_sets:
        release_str = s.get("release_date")
        if not release_str:
            continue
        try:
            release = date.fromisoformat(release_str)
        except ValueError:
            continue
        # Only sets that have already shipped (skip future releases —
        # 'coming soon' posts belong to the regular news feed, not the
        # overview stream).
        if release > today or release < cutoff:
            continue
        # Skip empty catalog rows (JP-side TCGdex stubs sometimes ship
        # with a release date but no cards). No cards = no post.
        if (s.get("card_count") or 0) < 5:
            log.info(
                "set_overview: skip %s (card_count=%s < 5)",
                s.get("id"), s.get("card_count"),
            )
            continue
        fresh_sets.append(s)

    if not fresh_sets:
        log.info(
            "set_overview: no sets released in the last %d days",
            NEW_SET_WINDOW_DAYS,
        )
        return []

    # Newest first, capped. If several sets ship on the same day
    # (JP-EN parallels), MAX_SETS_PER_RUN keeps the batch reasonable.
    fresh_sets.sort(key=lambda s: s.get("release_date", ""), reverse=True)
    fresh_sets = fresh_sets[:MAX_SETS_PER_RUN]

    items: list[NewsItem] = []
    for s in fresh_sets:
        set_id = s.get("id")
        set_name = s.get("name") or set_id
        top = await _fetch_json(
            urljoin(base, f"sets/{set_id}/cards"),
            {"sort": "price_desc", "page_size": TOP_CARDS_PER_SET},
        )
        top_cards = (top or {}).get("items", []) if isinstance(top, dict) else []
        if not top_cards:
            log.info("set_overview: skip %s (no cards on top-price fetch)", set_id)
            continue

        payload = {
            "set": {
                "id": set_id,
                "name": set_name,
                "series": s.get("series"),
                "release_date": s.get("release_date"),
                "printed_total": s.get("printed_total"),
                "total": s.get("total"),
                "logo_url": s.get("logo_url"),
                "symbol_url": s.get("symbol_url"),
                "total_value_usd": s.get("total_value_usd"),
                "card_count": s.get("card_count"),
            },
            "top_cards": top_cards,
        }

        # Inline images = the top-priced cards so the generator can
        # weave them in near their write-up.
        inline: list[dict[str, str]] = []
        for c in top_cards[:8]:
            img = c.get("image_small") or c.get("image_large")
            if img:
                inline.append({"url": img[:512], "caption": (c.get("name") or "")[:120]})

        hero = s.get("logo_url") or (
            top_cards[0].get("image_large") if top_cards else None
        )

        items.append(
            NewsItem(
                url=f"pulllist://set-overview/{set_id}",
                title=f"Set Overview — {set_name}",
                summary=(
                    f"{set_name} shipped {s.get('release_date')}. "
                    f"Top {len(top_cards)} cards by market price."
                ),
                source_name="set_overview",
                source_lang="en",
                published_at=today.isoformat(),
                raw_text=json.dumps(payload),
                hero_image_url=hero,
                inline_images=inline,
            )
        )

    log.info(
        "set_overview: emitted %d set overview item(s) from %d fresh sets",
        len(items), len(fresh_sets),
    )
    return items
