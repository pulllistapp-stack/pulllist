"""Login + draft POST against the PullList REST API.

Bot logs in fresh every run — no token caching. JWT TTL stops being a
concern, and a rotated NEWSBOT_ADMIN_PASSWORD takes effect on the
next run with no extra state to clear.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("newsbot.publisher")

# Render free tier sleeps after 15 min of idle and takes up to ~50s to
# wake. The bot runs once a day, so login is almost always the cold-
# start hit. 90s gives the backend room to boot before httpx times out.
REQUEST_TIMEOUT = 90.0


class PublisherError(RuntimeError):
    pass


async def login(api_base: str, email: str, password: str) -> str:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(
            f"{api_base}/auth/login",
            json={"email": email, "password": password},
        )
        if r.status_code != 200:
            raise PublisherError(
                f"login failed: {r.status_code} {r.text[:200]}"
            )
        token = r.json().get("access_token")
        if not token:
            raise PublisherError(f"login response missing access_token: {r.text[:200]}")
        return token


async def publish_draft(
    api_base: str, token: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """POST a new draft. payload must already match the PostIn schema
    (slug, title, body, status='draft', etc)."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(
            f"{api_base}/news/posts",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        if r.status_code == 409:
            # Slug collision — caller picks a new slug and retries.
            raise PublisherError(f"slug collision: {payload.get('slug')!r}")
        if r.status_code not in (200, 201):
            raise PublisherError(
                f"publish failed: {r.status_code} {r.text[:300]}"
            )
        return r.json()
