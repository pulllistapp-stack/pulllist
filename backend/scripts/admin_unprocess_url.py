"""Admin tool — remove URLs from the newsbot's persistent dedupe log
so the next bot run re-discovers and re-generates them.

Two modes:
  - substring match: `UNPROCESS_PATTERN=30th-celebration` removes
    every processed_url whose value contains the substring.
  - exact URL: `UNPROCESS_URL=https://...` removes only that URL.

Use when an earlier draft was bad (old prompt, source enricher
miss, etc.) and we want the bot to regenerate from the same source
under the fixed pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import urllib.parse

import httpx

from newsbot.config import settings
from newsbot.publisher import login

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("admin_unprocess_url")


async def main() -> int:
    pattern = os.environ.get("UNPROCESS_PATTERN", "").strip()
    exact = os.environ.get("UNPROCESS_URL", "").strip()
    if not pattern and not exact:
        log.error("Set UNPROCESS_PATTERN=<substring> or UNPROCESS_URL=<full URL>")
        return 1

    token = await login(
        settings.pulllist_api_base,
        settings.newsbot_admin_email,
        settings.newsbot_admin_password,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch the full processed_urls map regardless of mode — for
        # exact URL we still log "matched: X" so the CI run shows
        # whether the removal actually applied to a stored row.
        r = await client.get(
            f"{settings.pulllist_api_base}/news/posts/processed-urls",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        all_urls = list(r.json().keys())

        if exact:
            targets = [exact] if exact in all_urls else []
            log.info("exact: %s → %d match", exact[:80], len(targets))
        else:
            targets = [u for u in all_urls if pattern.lower() in u.lower()]
            log.info(
                "pattern %r → %d matches of %d total processed urls",
                pattern, len(targets), len(all_urls),
            )

        if not targets:
            log.warning("nothing matched, nothing to do")
            return 0

        for url in targets:
            params = {"source_url": url}
            d = await client.delete(
                f"{settings.pulllist_api_base}/news/posts/processed-urls",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if d.status_code in (204, 200):
                log.info("removed: %s", url[:120])
            else:
                log.error("delete failed %d for %s: %s",
                          d.status_code, url[:80], d.text[:200])

    log.info("done — %d url(s) removed", len(targets))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
