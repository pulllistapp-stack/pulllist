"""One-off — delete a single news post by slug via admin auth.
Same pattern as admin_dump_post; companion tool for regen workflows
where we delete a draft so dedupe sees its source_url as fresh again
and the next bot run will re-process it.

Reads NEWSBOT_ADMIN_EMAIL + NEWSBOT_ADMIN_PASSWORD + PULLLIST_API_BASE
+ DELETE_SLUG from env.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("admin_delete_post")

API_BASE = os.environ.get("PULLLIST_API_BASE", "https://api.pulllist.org/api/v1")
EMAIL = os.environ.get("NEWSBOT_ADMIN_EMAIL", "")
PASSWORD = os.environ.get("NEWSBOT_ADMIN_PASSWORD", "")
SLUG = os.environ.get("DELETE_SLUG", "")


async def main() -> int:
    if not SLUG:
        log.error("DELETE_SLUG env var not set")
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
        log.info("logged in as %s", EMAIL)

        r = await client.delete(
            f"{API_BASE}/news/posts/{SLUG}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code in (200, 204):
            log.info("deleted post slug=%s (status=%d)", SLUG, r.status_code)
            return 0
        if r.status_code == 404:
            log.warning("post slug=%s not found — nothing to delete", SLUG)
            return 0
        log.error("delete failed: %d %s", r.status_code, r.text[:200])
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
