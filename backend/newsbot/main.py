"""Newsbot entry point. Crawl → dedupe → classify → generate →
fact-check → publish-as-draft. Dry-run mode does everything except
the final POST, so CI can exercise the whole pipeline without
inserting rows.

Run locally:
    python -m newsbot.main

Run dry:
    DRY_RUN=1 python -m newsbot.main

GH Actions invokes this via .github/workflows/daily-newsbot.yml.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

from .classify import classify, slugify
from .config import settings
from .dedupe import filter_unseen
from .factcheck import verify_claims
from .generator import generate_article
from .publisher import PublisherError, login, publish_draft
from .sources import NewsItem, crawl_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("newsbot.main")


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _build_post_payload(
    item: NewsItem, article, category: str
) -> dict:
    return {
        "slug": slugify(article.title),
        "title": article.title,
        "body": article.body_markdown,
        "excerpt": article.excerpt,
        "region": "all",
        "category": category,
        "thumbnail_url": None,
        "author": settings.bot_author_name,
        "published_at": item.published_at or _today_iso(),
        "reading_time": article.reading_time,
        "status": "draft",
        "source_url": item.url,
    }


async def _process_item(
    item: NewsItem, api_base: str, token: str | None
) -> dict | None:
    """Returns a summary dict on success, None on reject."""
    category = classify(item)
    log.info("classify %r → %s", item.title, category)

    try:
        article = await generate_article(item)
    except Exception as exc:
        log.exception("generator failed for %s: %s", item.url, exc)
        return None

    verdict = await verify_claims(article.claims)
    if not verdict.passed:
        log.warning(
            "fact-check rejected %r — 0/%d claims corroborated",
            article.title,
            len(article.claims),
        )
        return None

    payload = _build_post_payload(item, article, category)

    if settings.dry_run or token is None:
        log.info(
            "[DRY RUN] would publish: slug=%s title=%r category=%s claims=%d",
            payload["slug"],
            payload["title"],
            category,
            len(article.claims),
        )
        return {"slug": payload["slug"], "title": payload["title"], "dry_run": True}

    try:
        resp = await publish_draft(api_base, token, payload)
    except PublisherError as exc:
        log.error("publish failed for %s: %s", payload["slug"], exc)
        return None

    log.info("published draft slug=%s", resp.get("slug"))
    return {"slug": resp.get("slug"), "title": resp.get("title"), "dry_run": False}


async def run() -> int:
    log.info(
        "newsbot starting dry_run=%s limit=%d api=%s",
        settings.dry_run,
        settings.daily_post_limit,
        settings.pulllist_api_base,
    )

    items = await crawl_all()
    if not items:
        log.warning("no items crawled — exiting cleanly")
        return 0

    # Login is needed for dedupe (admin source-urls map) AND publish.
    # Dry-run still logs in so 401s surface in CI before live runs.
    if not settings.newsbot_admin_password:
        log.error("NEWSBOT_ADMIN_PASSWORD is empty — cannot proceed")
        return 1

    try:
        token = await login(
            settings.pulllist_api_base,
            settings.newsbot_admin_email,
            settings.newsbot_admin_password,
        )
    except PublisherError as exc:
        log.error("login failed: %s", exc)
        return 1
    log.info("logged in as %s", settings.newsbot_admin_email)

    fresh = await filter_unseen(items, settings.pulllist_api_base, token)
    if not fresh:
        log.info("nothing new today — exiting cleanly")
        return 0

    selected = fresh[: settings.daily_post_limit]
    log.info("processing %d / %d fresh items", len(selected), len(fresh))

    publish_token = None if settings.dry_run else token
    results = []
    for item in selected:
        result = await _process_item(
            item, settings.pulllist_api_base, publish_token
        )
        if result:
            results.append(result)

    log.info(
        "newsbot done — published=%d rejected=%d dry_run=%s",
        len(results),
        len(selected) - len(results),
        settings.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
