"""One-off admin tool — wrap raw external thumbnail URLs through
images.weserv.nl so cross-origin browser loads aren't blocked by
hot-link-protected sources (PokeBeach et al).

Self-healing: lists every post (including drafts), skips any whose
thumbnail is already proxied / null / hosted on the PullList domain,
and PUTs back only the ones that needed wrapping. Re-running is a
no-op.

Reads NEWSBOT_ADMIN_EMAIL + NEWSBOT_ADMIN_PASSWORD + PULLLIST_API_BASE
from env — same secrets the daily-newsbot workflow uses, so the
GitHub Actions runner already has them when it invokes this script.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import urllib.parse

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("admin_proxy_thumbnails")

API_BASE = os.environ.get(
    "PULLLIST_API_BASE", "https://api.pulllist.org/api/v1"
)
EMAIL = os.environ.get("NEWSBOT_ADMIN_EMAIL", "")
PASSWORD = os.environ.get("NEWSBOT_ADMIN_PASSWORD", "")

# Anything matching one of these substrings in thumbnail_url is left
# alone — already proxied or hosted on a domain we trust to allow
# cross-origin loads.
SKIP_HOSTS = ("images.weserv.nl", "pulllist.org", "vercel.app")

REQUEST_TIMEOUT = 90.0  # Render cold start headroom

WESERV = "https://images.weserv.nl/?url={}"


def _wrap(url: str) -> str:
    stripped = url.split("://", 1)[-1]
    return WESERV.format(urllib.parse.quote(stripped, safe="/.-_~"))[:480]


def _needs_proxy(thumb: str | None) -> bool:
    if not thumb:
        return False
    return not any(h in thumb for h in SKIP_HOSTS)


async def _login(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{API_BASE}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError(f"login response missing access_token: {r.text[:200]}")
    return token


async def _list_all_posts(
    client: httpx.AsyncClient, token: str
) -> list[dict]:
    r = await client.get(
        f"{API_BASE}/news/posts?include_drafts=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()


async def _put_post(
    client: httpx.AsyncClient,
    token: str,
    slug: str,
    payload: dict,
) -> None:
    r = await client.put(
        f"{API_BASE}/news/posts/{slug}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    r.raise_for_status()


def _payload_from(post: dict, new_thumb: str) -> dict:
    """Strip the response back into a PostIn-shaped body with the new
    thumbnail. Match the API's required fields verbatim."""
    return {
        "slug": post["slug"],
        "title": post["title"],
        "body": post["body"],
        "excerpt": post.get("excerpt"),
        "region": post.get("region", "all"),
        "category": post.get("category"),
        "thumbnail_url": new_thumb,
        "author": post.get("author"),
        "published_at": post["published_at"],
        "reading_time": post.get("reading_time"),
        "status": post.get("status", "published"),
        "source_url": post.get("source_url"),
    }


async def main() -> int:
    if not EMAIL or not PASSWORD:
        log.error("NEWSBOT_ADMIN_EMAIL / NEWSBOT_ADMIN_PASSWORD not set")
        return 1

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        token = await _login(client)
        log.info("logged in as %s", EMAIL)

        posts = await _list_all_posts(client, token)
        log.info("found %d total posts (incl. drafts)", len(posts))

        fixed = 0
        for p in posts:
            thumb = p.get("thumbnail_url")
            if not _needs_proxy(thumb):
                log.info("skip %s (thumb=%r)", p["slug"], thumb)
                continue
            wrapped = _wrap(thumb)
            log.info(
                "wrap %s\n    old=%s\n    new=%s",
                p["slug"], thumb, wrapped,
            )
            await _put_post(client, token, p["slug"], _payload_from(p, wrapped))
            fixed += 1

        log.info("done — %d posts updated, %d skipped", fixed, len(posts) - fixed)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
