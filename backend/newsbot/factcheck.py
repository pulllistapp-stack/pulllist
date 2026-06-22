"""Minimal-viable fact-check via Tavily.

For each generated claim, run a Tavily search. If a claim returns zero
results we count it as unverified. Per SPEC: if ALL claims are
unverified, reject the article (don't publish). Numeric-tolerance
matching (±30% for prices) is deferred to Phase 2 — Phase 1 just
needs to catch the case where Claude invented something whole-cloth.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel
from tavily import AsyncTavilyClient

from .config import settings

log = logging.getLogger("newsbot.factcheck")


class ClaimResult(BaseModel):
    claim: str
    corroborating_urls: list[str] = []

    @property
    def verified(self) -> bool:
        return bool(self.corroborating_urls)


class Verdict(BaseModel):
    results: list[ClaimResult]
    passed: bool


async def verify_claims(claims: list[str]) -> Verdict:
    if not claims:
        # No claims to verify — generator chose to emit none. Treat as
        # pass; the article is presumably narrative-only.
        return Verdict(results=[], passed=True)

    if settings.skip_factcheck or not settings.tavily_api_key:
        log.warning("factcheck skipped (skip_factcheck=%s, api_key_set=%s)",
                    settings.skip_factcheck, bool(settings.tavily_api_key))
        return Verdict(
            results=[ClaimResult(claim=c) for c in claims],
            passed=True,
        )

    client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    results: list[ClaimResult] = []
    for claim in claims:
        try:
            r = await client.search(
                query=claim, max_results=3, search_depth="basic"
            )
            urls = [item.get("url", "") for item in r.get("results", []) if item.get("url")]
            results.append(ClaimResult(claim=claim, corroborating_urls=urls))
            log.info("claim %r — %d corroborating urls", claim, len(urls))
        except Exception as exc:
            log.exception("tavily search failed for claim %r: %s", claim, exc)
            results.append(ClaimResult(claim=claim, corroborating_urls=[]))

    # Pass if at least one claim got SOME corroboration. Reject the
    # whole article only if every claim came back empty — that's the
    # signal Claude likely fabricated.
    passed = any(r.verified for r in results)
    return Verdict(results=results, passed=passed)
