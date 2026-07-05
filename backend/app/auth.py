"""Auth utilities — password hashing, JWT encode/decode, FastAPI dependency."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import RefreshToken, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    """Returns the user id from a valid token, raises HTTPException otherwise."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token"
        )
    return user_id


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user_id = decode_token(creds.credentials)
    user = await db.get(User, user_id)
    if not user or user.deleted_at is not None:
        # Reject deleted users the same way as missing — same 401, so a
        # soft-deleted user can't fingerprint by error message.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


async def get_current_user_optional(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if creds is None:
        return None
    try:
        user_id = decode_token(creds.credentials)
    except HTTPException:
        return None
    user = await db.get(User, user_id)
    if user and user.deleted_at is not None:
        return None
    return user


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Gate admin-only endpoints (e.g. /news/posts mutations). Builds on
    the existing JWT auth and just adds the is_admin check; promote a
    user by setting is_admin=true directly in the DB (no signup-time
    elevation)."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user


async def get_current_admin_optional(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User | None:
    """Like get_current_admin but never raises — returns None for
    unauthenticated or non-admin requests. Lets endpoints branch on
    'is this an admin?' without forcing every public caller to send a
    token (e.g. GET /news/posts hides drafts from anon traffic but
    surfaces them when an admin opts in)."""
    if user is None or not user.is_admin:
        return None
    return user


# ────────── Refresh-token machinery ──────────


def hash_refresh_token(plaintext: str) -> str:
    """sha256 hex of the plaintext refresh token. Stored in the DB so a
    dump can't be replayed as a session."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def get_device_label(user_agent: str | None) -> str:
    """Best-effort human label for the /auth/sessions surface. Not
    security-relevant — a lying UA just gets a wrong label."""
    if not user_agent:
        return "Unknown device"
    ua = user_agent

    if "Windows" in ua:
        os_ = "Windows"
    elif "iPhone" in ua:
        os_ = "iPhone"
    elif "iPad" in ua:
        os_ = "iPad"
    elif "Android" in ua:
        os_ = "Android"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_ = "macOS"
    elif "Linux" in ua:
        os_ = "Linux"
    else:
        os_ = "Unknown OS"

    # Order matters — Edge and Chrome both ship "Chrome/" in UA, only
    # Edge adds "Edg/" so test it first. Same for Chrome-vs-Safari.
    if "Edg/" in ua:
        browser = "Edge"
    elif "Chrome/" in ua and "Chromium/" not in ua:
        browser = "Chrome"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Safari/" in ua and "Chrome/" not in ua:
        browser = "Safari"
    else:
        browser = "browser"

    return f"{browser} on {os_}"


async def create_refresh_token(
    db: AsyncSession,
    user_id: str,
    user_agent: str | None,
) -> str:
    """Mint a fresh refresh token, persist its hash, return the plaintext.

    Plaintext is what the browser cookie carries. The DB only ever sees
    the sha256 — so a snapshot of `refresh_tokens` is worthless without
    the cookie jars of every user.
    """
    plaintext = secrets.token_urlsafe(48)
    now = datetime.utcnow()
    row = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=hash_refresh_token(plaintext),
        created_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        device_label=get_device_label(user_agent),
        last_used_at=now,
    )
    db.add(row)
    await db.commit()
    return plaintext


async def rotate_refresh_token(
    db: AsyncSession,
    presented_plaintext: str,
    user_agent: str | None,
) -> tuple[str, User]:
    """Consume a presented refresh token, mint a new one. Returns
    (new_plaintext, user). Raises 401 on any failure.

    Detects reuse of a revoked token as a theft signal and revokes every
    remaining live token for that user — the attacker AND the legitimate
    holder both get booted and have to re-login. This is the standard
    reuse-detection rule; the false-positive cost (occasional forced
    re-login) is tiny next to the value of catching a stolen cookie.
    """
    if not presented_plaintext:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    token_hash = hash_refresh_token(presented_plaintext)
    row = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
    ).scalar_one_or_none()

    now = datetime.utcnow()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if row.revoked_at is not None:
        # Reuse-detected: nuke every live token this user still has. The
        # legitimate client will re-login and be fine; the attacker's
        # copy of the cookie stops working. We commit before raising so
        # the revocation is durable even if the client retries.
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == row.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked",
        )

    if row.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    user = await db.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Retire the presented row, mint a new one. Keep the original device
    # label so a session stays labelled as the same device across
    # rotations (UA can drift between requests — Chrome updates, etc.).
    row.revoked_at = now
    row.last_used_at = now

    new_plaintext = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=hash_refresh_token(new_plaintext),
            created_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            device_label=row.device_label or get_device_label(user_agent),
            last_used_at=now,
        )
    )
    await db.commit()
    return new_plaintext, user


async def revoke_refresh_token(
    db: AsyncSession,
    presented_plaintext: str | None,
) -> None:
    """Revoke a specific refresh token by plaintext. Silently no-ops for
    missing / already-dead tokens — logout should always succeed
    client-side regardless of server-side state."""
    if not presented_plaintext:
        return
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(presented_plaintext),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.utcnow())
    )
    await db.commit()


async def revoke_all_user_refresh_tokens(
    db: AsyncSession,
    user_id: str,
) -> int:
    """Kill every live refresh token for a user. Returns how many rows
    were flipped from live → revoked. Powers 'log out of all devices'."""
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.utcnow())
    )
    await db.commit()
    return result.rowcount or 0


# ────────── Refresh cookie helpers ──────────
#
# Starlette's Response.set_cookie() doesn't accept a `partitioned` argument
# yet, but Chrome's CHIPS third-party cookie rules (2024+) require the
# `Partitioned` attribute for cross-site cookies on Vercel↔Render. So we
# build the Set-Cookie header string by hand and append it to the response.


def _refresh_cookie_str(value: str, max_age: int) -> str:
    """Build the Set-Cookie value. In production we ship the full CHIPS
    package: Secure + SameSite=None + Partitioned. In dev (localhost)
    we relax to SameSite=Lax and drop Secure so cookies flow over http."""
    in_prod = settings.env != "development"
    parts = [
        f"{settings.refresh_cookie_name}={value}",
        f"Max-Age={max_age}",
        "Path=/api/v1/auth",
        "HttpOnly",
    ]
    if in_prod:
        parts += ["Secure", "SameSite=None", "Partitioned"]
    else:
        # localhost:3000 ↔ localhost:8000 is cross-origin but same-site,
        # so Lax lets the cookie ride refresh calls without Secure/HTTPS.
        parts += ["SameSite=Lax"]
    return "; ".join(parts)


def set_refresh_cookie(response: Response, token: str) -> None:
    max_age = settings.refresh_token_expire_days * 24 * 60 * 60
    response.headers.append("set-cookie", _refresh_cookie_str(token, max_age))


def clear_refresh_cookie(response: Response) -> None:
    response.headers.append("set-cookie", _refresh_cookie_str("", 0))
