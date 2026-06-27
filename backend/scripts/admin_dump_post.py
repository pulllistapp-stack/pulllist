"""One-off — dump full body of a draft (or any) post by slug,
including admin-only fields. Reads NEWSBOT_ADMIN_EMAIL +
NEWSBOT_ADMIN_PASSWORD + PULLLIST_API_BASE from env.

Usage (in CI via workflow_dispatch):
    python -m scripts.admin_dump_post <slug>
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("admin_dump_post")

API_BASE = os.environ.get("PULLLIST_API_BASE", "https://api.pulllist.org/api/v1")
EMAIL = os.environ.get("NEWSBOT_ADMIN_EMAIL", "")
PASSWORD = os.environ.get("NEWSBOT_ADMIN_PASSWORD", "")
SLUG = os.environ.get("DUMP_SLUG", "")


async def main() -> int:
    if not SLUG:
        log.error("DUMP_SLUG env var not set")
        return 1
    if not EMAIL or not PASSWORD:
        log.error("NEWSBOT_ADMIN_EMAIL / NEWSBOT_ADMIN_PASSWORD not set")
        return 1
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            f"{API_BASE}/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        r.raise_for_status()
        token = r.json()["access_token"]
        r = await client.get(
            f"{API_BASE}/news/posts/{SLUG}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        p = r.json()
        print(f"=== SLUG: {p['slug']}")
        print(f"=== TITLE: {p['title']}")
        print(f"=== STATUS: {p.get('status')}")
        print(f"=== SOURCE: {p.get('source_url')}")
        print(f"=== THUMBNAIL: {p.get('thumbnail_url')}")
        print(f"=== BODY:")
        print(p["body"])
        print(f"=== END BODY (word count: {len(p['body'].split())})")
        # Count and list embedded images
        img_count = p["body"].count("![")
        print(f"=== embedded ![](...) count: {img_count}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
