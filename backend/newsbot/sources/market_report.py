"""Weekly market movers report source.

Phase B Sprint 1 — first data-driven source. Hits our own
/cards/trending endpoint for gainers + losers over the last 7 days
and packages them into a single NewsItem the generator turns into
a 'Weekly Movers' post (Collectory-style: emoji-tagged tables,
card-links back to /cards/{id}, takeaway + catalog CTA).

Off by default — only runs when the weekly cron flips
market_report_enabled=True. daily-newsbot.yml doesn't enable it,
so the everyday news feed keeps its regular shape; the Monday
market-report workflow is what turns it on.

Why go through the HTTP endpoint instead of hitting the DB
directly? /cards/trending already does the hard work — MAD-ratio
filtering, penny-stock exclusion, per-variant dedupe, era/tier
filters. Duplicating that logic here would either drift out of
sync or force us to re-test the noise-filters. HTTP is fine —
the payload is small and the request runs once per report.
"""
from __future__ import annotations

import json
import logging
from urllib.parse import urljoin

import httpx

from ..config import settings
from . import NewsItem, register

log = logging.getLogger("newsbot.sources.market_report")

REQUEST_TIMEOUT = 60.0  # trending computes on demand; 60s covers cold DB
# What we ask /cards/trending for. Tuned for the 'weekly digest' feel:
# 7-day window, chase-tier so we get the story-worthy cards (not $6
# common price wobble), $5-$300 band so a single Umbreon $8000 pull
# doesn't dominate the whole list.
_MOVERS_QUERY = {
    "period_days": 7,
    "source": "ebay",
    "limit": 10,
    "min_price_usd": 5.0,
    "max_price_usd": 300.0,
    "tier": "chase",
    "era": "modern",
}


async def _fetch_movers(direction: str) -> list[dict]:
    """Fetch top gainers OR losers. Returns [] on any failure — the
    generator will render 'no data' rather than the whole report
    dying because eBay had a slow snapshot cadence this week."""
    # /cards/trending sits at the api base one level up from /news/,
    # so we strip the trailing '/api/v1' path suffix cleanly.
    base = settings.pulllist_api_base
    url = urljoin(base.rstrip("/") + "/", f"cards/trending")
    params = {**_MOVERS_QUERY, "direction": direction}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            log.warning(
                "market_report: trending %s → %d %s",
                direction, r.status_code, r.text[:200],
            )
            return []
        data = r.json()
    except Exception as exc:
        log.exception("market_report: fetch %s failed: %s", direction, exc)
        return []
    return data.get("movers", []) or []


def _iso_week_id(today_iso: str) -> str:
    """YYYY-Www label for the weekly-report source_url so cross-run
    dedupe (processed_urls) can trivially skip a re-trigger of the
    same week. today_iso is passed in for testability — real caller
    uses date.today()."""
    from datetime import date as _date
    y, m, d = (int(x) for x in today_iso.split("-"))
    yr, wk, _ = _date(y, m, d).isocalendar()
    return f"{yr}-W{wk:02d}"


@register("market_report")
async def crawl() -> list[NewsItem]:
    """Emit ONE NewsItem representing this week's market-report
    post. The generator turns it into a full Collectory-style
    Movers article. Skipped when settings.market_report_enabled is
    False so the daily cron doesn't accidentally generate one."""
    if not getattr(settings, "market_report_enabled", False):
        log.info("market_report: disabled (MARKET_REPORT_ENABLED=1 to enable)")
        return []

    gainers = await _fetch_movers("up")
    losers = await _fetch_movers("down")

    if not gainers and not losers:
        log.warning(
            "market_report: 0 gainers + 0 losers — skipping report entirely"
        )
        return []

    from datetime import date as _date
    today = _date.today().isoformat()
    week_id = _iso_week_id(today)

    # Package the payload in raw_text as a compact JSON blob the
    # generator's market_report branch parses. Keeping it as JSON
    # (not prose) makes the prompt deterministic — the model doesn't
    # have to fish numbers out of a paragraph.
    payload = {
        "week_id": week_id,
        "period_days": _MOVERS_QUERY["period_days"],
        "source": _MOVERS_QUERY["source"],
        "gainers": gainers,
        "losers": losers,
    }

    # source_url is a synthetic per-week key so processed_urls dedupe
    # works: any re-trigger of the same ISO week is a no-op.
    synthetic_url = f"pulllist://market-report/{week_id}"

    # Populate inline_images with the top mover images so the generator
    # has something concrete to weave in. Card links are handled in the
    # generator branch (which knows the /cards/{id} pattern).
    inline: list[dict[str, str]] = []
    for mover in (gainers + losers)[:8]:
        img = mover.get("image_small")
        if img:
            inline.append({
                "url": img[:512],
                "caption": mover.get("name", "")[:120],
            })

    log.info(
        "market_report: week=%s gainers=%d losers=%d",
        week_id, len(gainers), len(losers),
    )
    return [
        NewsItem(
            url=synthetic_url,
            title=f"PullList Weekly Movers — Week {week_id}",
            summary=(
                f"Top {len(gainers)} gainers and {len(losers)} losers "
                f"on eBay over the last {_MOVERS_QUERY['period_days']} days, "
                f"chase rarity, $5-$300 band."
            ),
            source_name="market_report",
            source_lang="en",
            published_at=today,
            raw_text=json.dumps(payload),
            hero_image_url=(
                (gainers[0].get("image_small") if gainers else None)
                or (losers[0].get("image_small") if losers else None)
            ),
            inline_images=inline,
        )
    ]
