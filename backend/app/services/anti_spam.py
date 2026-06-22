"""Cheap, layered defenses for the signup endpoint.

Three checks, applied in order before we touch the DB:

  1. Honeypot field — frontend renders a hidden `website` input. A real
     human never sees it; bots that fire form-fills on every input
     populate it.
  2. Per-IP rate limit — N signups per rolling window per source IP.
     In-memory dict, single-process. Fine for a single-Render-dyno
     deploy; revisit when we scale out.
  3. Disposable email blocklist — known throwaway providers (tempmail,
     10minutemail, etc.) are rejected at the email domain layer.

Together this blocks the obvious wave of bot signups + low-effort
abuse. For higher-tier defense (CAPTCHA, email verification,
proof-of-work) see the Phase 2 / Phase 3 notes in the spec.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

log = logging.getLogger("anti_spam")


# ────────────── Honeypot ──────────────


def check_honeypot(website_field: str | None) -> None:
    """Raise 400 if the honeypot field has content. Always-empty is the
    only legitimate state."""
    if website_field is not None and website_field.strip() != "":
        log.info("signup blocked: honeypot tripped")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signup failed. Please try again.",
        )


# ────────────── Rate limit ──────────────

# IP -> deque of recent signup timestamps. Trimmed on each check so old
# entries don't pile up forever. Module-global because we want one
# shared bucket across all requests in a worker.
_SIGNUP_BUCKETS: dict[str, deque[float]] = defaultdict(deque)

# 5 signups per IP per hour is plenty for a household / coffee shop
# sharing one NAT; bots trying to farm accounts hit the wall fast.
_LIMIT = 5
_WINDOW_SECONDS = 60 * 60


def _client_ip(request: Request) -> str:
    """Best-effort client IP. Render / Vercel both terminate TLS upstream
    so the real client lives in X-Forwarded-For; fall back to request
    client when the header is absent (e.g. local dev)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # Comma-separated chain — first entry is the original client.
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    """Token-bucket-ish: keep a deque of recent timestamps per IP, drop
    entries older than the window, then check len(). 429 once full."""
    now = time.time()
    ip = _client_ip(request)
    bucket = _SIGNUP_BUCKETS[ip]
    # Trim expired
    while bucket and now - bucket[0] > _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= _LIMIT:
        log.info(f"signup blocked: rate limit hit for ip={ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again later.",
        )
    bucket.append(now)


# ────────────── Disposable email blocklist ──────────────

# Compact list of the most common disposable / throwaway email providers.
# Not exhaustive (the long tail is ~5,000 domains) but covers the
# providers that show up in real abuse signal. Extend as we see new ones.
_DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "10minutemail.com",
        "10minutemail.net",
        "20minutemail.com",
        "30minutemail.com",
        "anonbox.net",
        "burnermail.io",
        "discard.email",
        "dispostable.com",
        "fakeinbox.com",
        "getairmail.com",
        "guerrillamail.com",
        "guerrillamail.de",
        "guerrillamail.net",
        "guerrillamail.org",
        "guerrillamail.biz",
        "guerrillamailblock.com",
        "harakirimail.com",
        "incognitomail.org",
        "inboxalias.com",
        "inboxbear.com",
        "instantemailaddress.com",
        "jetable.org",
        "kasmail.com",
        "mailcatch.com",
        "maildrop.cc",
        "mailforspam.com",
        "mailinator.com",
        "mailinator.net",
        "mailnesia.com",
        "mailnull.com",
        "mintemail.com",
        "moakt.com",
        "mohmal.com",
        "mvrht.com",
        "mytemp.email",
        "nada.email",
        "no-spam.ws",
        "nowmymail.com",
        "objectmail.com",
        "onetimeemail.net",
        "pokemail.net",
        "rcpt.at",
        "sharklasers.com",
        "spam4.me",
        "spamgourmet.com",
        "spamspot.com",
        "sute.jp",
        "temp-mail.io",
        "temp-mail.org",
        "tempail.com",
        "tempinbox.com",
        "tempmail.de",
        "tempmail.net",
        "tempmail.us.com",
        "tempmailaddress.com",
        "tempmail.dev",
        "throwam.com",
        "throwaway.email",
        "throwawaymail.com",
        "tmail.ws",
        "tmpmail.org",
        "trashmail.com",
        "trashmail.de",
        "trashmail.net",
        "wegwerfmail.de",
        "wegwerfmail.org",
        "yopmail.com",
        "yopmail.fr",
        "yopmail.net",
        "zzz.com",
    }
)


def check_email_domain(email: str) -> None:
    """Reject signups from known throwaway email providers. Doesn't
    catch ALL of them — the full list is ~5k domains and we don't want
    to ship a megabyte of frozenset — but the providers above cover the
    real abuse traffic. Adversarial users can still register on
    'asd@sdfsd.com' style addresses; that's caught later via email
    verification (Phase 2)."""
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if domain in _DISPOSABLE_DOMAINS:
        log.info(f"signup blocked: disposable domain {domain}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This email provider isn't supported. Please use a "
                "permanent address."
            ),
        )
