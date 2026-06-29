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
import re
import sys
import urllib.parse
from datetime import datetime, timezone

from .classify import classify, slugify
from .config import settings
from .dedupe import filter_unseen
from .factcheck import verify_claims
from .generator import generate_article
from .publisher import PublisherError, login, publish_draft
from .sources import NewsItem, close_stealth_session, crawl_all, enrich_item

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("newsbot.main")


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


_WESERV = "https://images.weserv.nl/?url={}"
# Anything matching one of these hosts in an image URL bypasses the
# weserv wrap — already proxied, or hosted on a domain we trust to
# allow cross-origin loads (our own frontend, Vercel preview deploys).
_TRUSTED_IMAGE_HOSTS = ("images.weserv.nl", "pulllist.org", "vercel.app")


def _proxy_image(url: str | None) -> str | None:
    """Wrap external images through images.weserv.nl so cross-origin
    browser loads aren't blocked by hot-link-protected sources.

    PokeBeach (and most WordPress + Cloudflare setups) return 403 when
    the request's Referer header points at a different domain. weserv
    is a free, fast image CDN that strips the Referer and caches the
    result. Already-proxied or PullList-hosted URLs pass through so a
    re-run doesn't double-wrap. Caps at 480 chars to fit
    NewsPost.thumbnail_url's 512-char column with margin for the prefix.
    """
    if not url:
        return None
    # Safety net for data: / javascript: / file: etc. — weserv can
    # only fetch http(s). Earlier in the pipeline (Serper imageUrl
    # ingest) we already drop these, but anything that slipped past
    # would render as a broken image here.
    if not url.startswith(("http://", "https://")):
        return None
    if any(h in url for h in _TRUSTED_IMAGE_HOSTS):
        return url
    stripped = url.split("://", 1)[-1]
    return _WESERV.format(urllib.parse.quote(stripped, safe="/.-_~"))[:480]


# Matches markdown image syntax — captures the prefix `![alt](`, the
# URL, and the closing `)` (possibly with an optional title).
_MARKDOWN_IMG_RE = re.compile(r"(!\[[^\]]*\]\()\s*(\S+?)(\s+\"[^\"]*\")?(\s*\))")

# Matches an <img> tag's src="..." or src='...' attribute. Claude
# emits raw HTML when wrapping paired/split images in flex containers,
# so those URLs need the same weserv treatment as markdown images
# (otherwise cross-origin Referer 403s them in the browser).
_HTML_IMG_SRC_RE = re.compile(
    r"(<img[^>]*\s)(src=)([\"'])([^\"']+)(\3)",
    re.IGNORECASE,
)


def _proxy_inline_images(markdown: str) -> str:
    """Walk every image URL in the markdown body — both `![alt](url)`
    markdown and `<img src="url">` HTML — and wrap external ones
    through weserv (same hot-link bypass as thumbnail_url).

    Skips non-http URLs (relative paths, anchors, mailto: etc) and
    leaves trusted hosts alone. Idempotent on already-wrapped URLs.
    """
    def _wrap_md(m: re.Match) -> str:
        prefix, url, title, suffix = m.group(1), m.group(2), m.group(3) or "", m.group(4)
        if not url.startswith(("http://", "https://")):
            return m.group(0)
        wrapped = _proxy_image(url) or url
        return f"{prefix}{wrapped}{title}{suffix}"

    def _wrap_html(m: re.Match) -> str:
        head, src_eq, quote, url, close_quote = m.groups()
        if not url.startswith(("http://", "https://")):
            return m.group(0)
        wrapped = _proxy_image(url) or url
        return f"{head}{src_eq}{quote}{wrapped}{close_quote}"

    out = _MARKDOWN_IMG_RE.sub(_wrap_md, markdown)
    out = _HTML_IMG_SRC_RE.sub(_wrap_html, out)
    return out


def _build_post_payload(
    item: NewsItem, article, category: str
) -> dict:
    return {
        "slug": slugify(article.title),
        "title": article.title,
        "body": _proxy_inline_images(article.body_markdown),
        "excerpt": article.excerpt,
        "region": "all",
        "category": category,
        "thumbnail_url": _proxy_image(item.hero_image_url),
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

    # Crawlers that hand back URL-only cards (e.g. PokeBeach) fill
    # raw_text here. No-op for sources that already populate it.
    item = await enrich_item(item)
    if not item.raw_text:
        log.info(
            "enrich produced no body for %s — generator will work off title+summary",
            item.url,
        )

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


async def _run_body() -> int:
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


async def run() -> int:
    # Wrap the body so the shared Scrapling Stealth session (Chromium
    # subprocess) gets closed cleanly before asyncio.run() tears down
    # the event loop. Without this, Python's GC tries to clean up
    # the leaked subprocess after loop close → noisy 'RuntimeError:
    # Event loop is closed' in CI logs. Doesn't affect actual
    # publishing, just makes the log readable.
    try:
        return await _run_body()
    finally:
        await close_stealth_session()


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
