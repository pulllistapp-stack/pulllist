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

import httpx

from .classify import classify, slugify
from .config import settings
from .dedupe import filter_unseen, mark_processed
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
# weserv wrap — already proxied, hosted on a domain we trust to allow
# cross-origin loads (our own frontend, Vercel preview deploys), or
# explicitly blocked by weserv policy so wrapping would 400.
#
# pokemoncenter.com: weserv responds 400 "Domain or TLD blocked by
# policy" for this host. Their image CDN serves hot-link-friendly
# images directly off Amazon S3 (Referer-independent 200), so skipping
# the wrap is both necessary and safe.
_TRUSTED_IMAGE_HOSTS = (
    "images.weserv.nl",
    "pulllist.org",
    "vercel.app",
    "pokemoncenter.com",
    # pokemon.com news + press.pokemon.com both serve hero images
    # from these CDNs, and weserv 400s 'Domain or TLD blocked by
    # policy' on both — so we skip the wrap and use direct URLs,
    # which their CDNs serve hot-link-friendly off Amazon S3 /
    # Cloudfront. Added after dump showed 4 / 5 fresh items being
    # rejected with these hosts as the unwrap-able hero.
    "mcdn.pokemon.com",
    "imguscdn.gamespress.com",
)

# HEAD-check timeout for the pre-flight thumbnail verifier. Kept tight
# so a hung CDN never delays the whole run; failing the check just
# drops the item (no Claude tokens spent), which is the safer default.
THUMBNAIL_VERIFY_TIMEOUT = 10.0


async def _verify_thumbnail(url: str | None) -> bool:
    """Pre-flight HEAD check on the URL we're about to publish as the
    post thumbnail. Returns True only if the response is 200 AND the
    Content-Type is an image — guards against:

      - weserv 400 'Domain or TLD blocked by policy' (broke Pokemon
        Center thumbs before pokemoncenter.com was added to TRUSTED)
      - 404s when a hot-link source returns HTML error pages
      - non-image responses (login walls, captcha pages)
      - hung CDNs (10s timeout)

    A False here means we drop the item BEFORE Claude is called,
    so a broken-image source never burns generation tokens.

    Sends a browser-like Referer so origin CDNs with hot-link
    whitelists don't 403 a no-referer probe (the user's browser
    will send one too, so this matches what they'd actually see).
    """
    if not url:
        return False
    # Browser-shaped headers so origin CDNs that filter on UA don't
    # answer with their HTML default page (Pokemon Center's S3 image
    # CDN was returning 200/text/html for python-httpx requests
    # while returning 200/image/jpeg for curl — pure UA-gated).
    headers = {
        "Referer": "https://pulllist.org/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    try:
        async with httpx.AsyncClient(
            timeout=THUMBNAIL_VERIFY_TIMEOUT, follow_redirects=True
        ) as client:
            r = await client.head(url, headers=headers)
            # Some CDNs reject HEAD with 405 but answer GET. Fall back
            # to a 1-byte ranged GET so we don't false-negative those.
            if r.status_code in (403, 405):
                r = await client.get(
                    url, headers={**headers, "Range": "bytes=0-0"}
                )
    except Exception as exc:
        log.warning("thumbnail HEAD failed for %s: %s", url[:80], exc)
        return False
    ctype = r.headers.get("content-type", "").lower()
    # Trust an image extension in the URL even when the server's
    # content-type is wrong/missing — some CDNs return text/html on
    # HEAD for image paths (Pokemon Center S3 default page) but the
    # GET would still serve image bytes. Status filter (200/206) is
    # the real broken-vs-OK gate; content-type is a quality signal.
    url_path = url.lower().split("?", 1)[0]
    has_image_ext = url_path.endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
    )
    is_image = ctype.startswith("image/") or has_image_ext
    ok = r.status_code in (200, 206) and is_image
    if not ok:
        log.warning(
            "thumbnail verify reject: %s → %d %s",
            url[:80], r.status_code, ctype[:40],
        )
    return ok


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


# TCG-card priority — LO's PullList is a TCG card site, so card-
# related news (set reveals, booster releases, card-spec mechanics)
# should win selection over generic merch. Substring match against
# title + summary, case-insensitive. Hitting any keyword bumps the
# item once (no stacking — the bump is "this is on-topic", not
# "how on-topic"). Drift in set names is fine; the generic terms
# (booster/etb/preorder) catch most TCG news on their own.
_CARD_PRIORITY_KEYWORDS = (
    "tcg",
    "trading card",
    "booster",
    "elite trainer box",
    "etb",
    "premium collection",
    "preorder",
    "card reveal",
    "set release",
    "secret rare",
    "alternate art",
    "special illustration",
    "illustration rare",
    "vmax",
    "vstar",
    " ex ",
    " ex.",
    " v ",
    # current/recent set names (cheap heuristic — extend as new sets ship)
    "mega evolution",
    "ascended heroes",
    "storm emeralda",
    "prismatic evolutions",
    "surging sparks",
    "stellar crown",
    "black bolt",
    "white flare",
    "destined rivals",
    "journey together",
    "heavy hitters",
)

# Non-card merchandise — LO cares less about these for a TCG-focused
# feed. Doesn't reject (plush drops still count as Pokémon news),
# just downranks vs card content so card items win when both are
# fresh on the same day.
_NON_CARD_PENALTIES = (
    "plush",
    "stationery",
    "apparel",
    "keychain",
    "figurine",
    " doll",  # leading space — don't match "card holders" etc
    "mug",
    "blanket",
    "pillow",
    "playmat",
)


def _score_item(item: NewsItem, source_counts: dict[str, int]) -> int:
    """Composite ranking signal. Higher = picked first.

    Mix:
      + 10 if any TCG card keyword hit
      -  5 if any non-card merch keyword hit
      +  3 default bonus for editor-written PokeBeach articles
         (their hit rate on TCG-relevance is near-100% historically)
      -  4 per prior item already selected from the same source
         (round-robin: prevents the daily slate filling with one site)

    Tie-broken on input order — so within the same score bucket,
    the crawler's emit order wins (PokeBeach by-recency, Serper by
    relevance)."""
    haystack = (item.title + " " + (item.summary or "")).lower()
    score = 0
    if any(kw in haystack for kw in _CARD_PRIORITY_KEYWORDS):
        score += 10
    if any(kw in haystack for kw in _NON_CARD_PENALTIES):
        score -= 5
    if "pokebeach" in item.source_name.lower():
        score += 3
    prior = source_counts.get(item.source_name.lower(), 0)
    score -= prior * 4
    return score


def _select_for_publishing(
    fresh: list[NewsItem], limit: int
) -> list[NewsItem]:
    """Pick `limit` items from `fresh` favoring TCG card content and
    source diversity. Greedy: each round recompute source_counts
    against the already-picked slate, score everyone, take the
    leader. Recomputing per round is what makes the round-robin
    behavior emerge — without it the highest-default-bonus source
    would still monopolize the slate."""
    selected: list[NewsItem] = []
    pool = list(fresh)
    while pool and len(selected) < limit:
        source_counts: dict[str, int] = {}
        for s in selected:
            k = s.source_name.lower()
            source_counts[k] = source_counts.get(k, 0) + 1
        # Stable sort + reverse — same-score ties preserve input order.
        pool.sort(key=lambda i: _score_item(i, source_counts), reverse=True)
        selected.append(pool.pop(0))
    return selected


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
    """Returns a summary dict on success, None on reject. Every
    terminal state (publish, reject, error) logs the source_url to
    the persistent dedupe table so a future run never re-spends
    Claude tokens on a URL we've already decided about, even if the
    resulting draft was later deleted."""
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

    # Pre-flight thumbnail check — drop items that won't render an
    # image BEFORE Claude is called. LO doesn't want a draft sitting
    # in admin with a broken thumbnail (post-mortem of toy/Pokemon
    # Center runs that ate tokens for posts later deleted manually).
    # The proxied URL is what actually gets published, so verifying
    # *that* matches the user-browser fetch path exactly.
    candidate_thumb = _proxy_image(item.hero_image_url)
    if not await _verify_thumbnail(candidate_thumb):
        log.warning(
            "skip %s — no usable thumbnail (hero=%s)",
            item.url, (item.hero_image_url or "")[:80],
        )
        if token:
            await mark_processed(api_base, token, item.url, "thumbnail_failed")
        return None

    try:
        article = await generate_article(item)
    except Exception as exc:
        log.exception("generator failed for %s: %s", item.url, exc)
        if token:
            await mark_processed(api_base, token, item.url, "generator_error")
        return None

    verdict = await verify_claims(article.claims)
    if not verdict.passed:
        log.warning(
            "fact-check rejected %r — 0/%d claims corroborated",
            article.title,
            len(article.claims),
        )
        if token:
            await mark_processed(api_base, token, item.url, "factcheck_failed")
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
        if token:
            await mark_processed(api_base, token, item.url, "publish_error")
        return None

    log.info("published draft slug=%s", resp.get("slug"))
    # The post row already records the source_url, but we mirror it
    # to processed_urls so the dedupe set stays consistent even after
    # LO deletes the draft from the admin UI.
    await mark_processed(api_base, token, item.url, "published")
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

    selected = _select_for_publishing(fresh, settings.daily_post_limit)
    log.info(
        "processing %d / %d fresh items (selection: %s)",
        len(selected),
        len(fresh),
        ", ".join(f"{s.source_name}=1" for s in selected) or "none",
    )

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
