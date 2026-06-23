"""Check eBay API rate-limit headroom.

Hits eBay's Developer Analytics rate_limit endpoint so we can see how
much of today's Browse-API budget is left without burning a Browse
call to find out. Useful before a snapshot run, especially in the
narrow daily window we have on the free tier.

The Developer Analytics API needs its own OAuth scope
(`developer.analytics.readonly`), so we mint a separate
client_credentials token here rather than reusing EbayClient's
Browse-scoped one.

Run:
    python -m scripts.check_ebay_quota
"""
from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

_ANALYTICS_SCOPE = "https://api.ebay.com/oauth/api_scope/developer.analytics.readonly"


def _bar(used: int, limit: int, width: int = 30) -> str:
    if limit <= 0:
        return "?" * width
    filled = round(width * used / limit)
    return "█" * filled + "░" * (width - filled)


async def _get_token(client: httpx.AsyncClient) -> str:
    app_id = settings.ebay_active_app_id
    cert_id = settings.ebay_active_cert_id
    if not app_id or not cert_id:
        raise RuntimeError(
            f"eBay {settings.ebay_env} credentials missing. Set EBAY_APP_ID + "
            "EBAY_CERT_ID in backend/.env"
        )
    cred = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
    r = await client.post(
        f"{settings.ebay_base_url}/identity/v1/oauth2/token",
        data={"grant_type": "client_credentials", "scope": _ANALYTICS_SCOPE},
        headers={
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    if r.status_code != 200:
        raise RuntimeError(
            f"Token request failed {r.status_code}: {r.text[:300]}\n"
            "If the response says invalid_scope, the analytics scope isn't "
            "enrolled on this app — request it under "
            "https://developer.ebay.com/my/keys."
        )
    return r.json()["access_token"]


async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _get_token(client)
        r = await client.get(
            f"{settings.ebay_base_url}/developer/analytics/v1_beta/rate_limit/",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        if r.status_code != 200:
            print(f"Rate-limit query failed {r.status_code}: {r.text[:300]}")
            sys.exit(1)
        data = r.json()

    print(f"eBay {settings.ebay_env} rate limits")
    print("=" * 78)
    matched = False
    for entry in data.get("rateLimits", []):
        api_name = entry.get("apiName", "?")
        api_context = entry.get("apiContext", "?")
        for resource in entry.get("resources", []):
            res_name = resource.get("name", "?")
            for rate in resource.get("rates", []):
                limit = int(rate.get("limit") or 0)
                remaining = int(rate.get("remaining") or 0)
                used = limit - remaining
                window_s = int(rate.get("timeWindow") or 0)
                window_h = window_s / 3600 if window_s else 0
                reset = rate.get("reset", "?")
                # Highlight Browse — that's the one we care about for snapshots
                marker = "►" if "browse" in api_name.lower() else " "
                matched = True
                print(
                    f"{marker} {api_context:>10}.{api_name:<10} "
                    f"{res_name:<40} "
                    f"{used:>5}/{limit:<5}  [{_bar(used, limit)}]  "
                    f"window={window_h:.0f}h  reset={reset}"
                )
    if not matched:
        print("(no rate-limit entries returned — eBay may not have")
        print(" registered this app for analytics yet)")
    print("=" * 78)
    print("Legend: ► = Browse API (used by snapshot + live-listings)")


if __name__ == "__main__":
    asyncio.run(main())
