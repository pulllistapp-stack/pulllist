"""Auth routes — signup, login, google, refresh, logout, sessions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    hash_refresh_token,
    clear_refresh_cookie,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    revoke_all_user_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
    set_refresh_cookie,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import RefreshToken, User
from app.schemas.auth import (
    AccessTokenResponse,
    GoogleAuthRequest,
    LoginRequest,
    SessionInfo,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from app.services.anti_spam import (
    check_email_domain,
    check_honeypot,
    check_rate_limit,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _ua(request: Request) -> str | None:
    """Read the User-Agent header — used only for session labelling."""
    return request.headers.get("user-agent")


def _read_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(settings.refresh_cookie_name)


async def _issue_session(
    db: AsyncSession,
    user: User,
    request: Request,
    response: Response,
) -> TokenResponse:
    """Mint access JWT + refresh cookie for a freshly-authenticated user.
    Shared by /login, /signup, /google so all three entry points behave
    identically for token issuance."""
    access = create_access_token(user.id)
    refresh_plain = await create_refresh_token(db, user.id, _ua(request))
    set_refresh_cookie(response, refresh_plain)
    return TokenResponse(access_token=access, user=UserRead.model_validate(user))


@router.post("/signup", response_model=TokenResponse)
async def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Anti-spam stack — runs before any DB write so bot traffic costs
    # us nothing beyond the request handshake. Order is cheapest first:
    # honeypot (instant rejection), rate limit (in-memory check),
    # disposable email (set lookup).
    check_honeypot(payload.website)
    check_rate_limit(request)
    check_email_domain(payload.email)

    existing = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        id=str(uuid.uuid4()),
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return await _issue_session(db, user, request, response)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    # Google-only accounts have password_hash NULL - block the password
    # path with the same generic "incorrect" message so we don't leak
    # which accounts are Google-linked.
    if (
        not user
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    return await _issue_session(db, user, request, response)


@router.post("/google", response_model=TokenResponse)
async def google_login(
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Sign in (or sign up) with a Google Identity Services ID token.

    Single endpoint handles both: if no user matches, we create one;
    otherwise we link / log into the existing account. The frontend
    button calls the same URL whether the user is on /login or /signup.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on this server.",
        )

    try:
        # Verifies signature + expiry + audience in one call. Raises
        # ValueError on any mismatch - which is what we want; never let
        # an unverifiable token mint a session.
        claims = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google credential: {e}",
        )

    google_sub = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified", False)
    if not google_sub or not email or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token missing required identity claims.",
        )

    # Try to match by google_id first (stable across email changes),
    # then fall back to email (lets existing email/password accounts
    # link to Google on first Google sign-in instead of duplicating).
    user = (
        await db.execute(select(User).where(User.google_id == google_sub))
    ).scalar_one_or_none()
    if user is None:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=None,
            google_id=google_sub,
            name=claims.get("name"),
            avatar_url=claims.get("picture"),
        )
        db.add(user)
    else:
        # Link Google to an existing email-account on first Google sign-in,
        # and freshen profile fields from Google when we have nothing local.
        if user.google_id is None:
            user.google_id = google_sub
        if not user.name and claims.get("name"):
            user.name = claims.get("name")
        if not user.avatar_url and claims.get("picture"):
            user.avatar_url = claims.get("picture")

    await db.commit()
    await db.refresh(user)

    return await _issue_session(db, user, request, response)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """Rotate refresh cookie, hand back a fresh 15-min access JWT.

    Cookie is httpOnly so JS never sees it — the browser attaches it
    automatically when the frontend calls with `credentials: 'include'`.
    CORS allowlist + SameSite=None is our CSRF perimeter for now; if we
    ever need deeper defence we can layer a double-submit token on top
    without changing the endpoint shape.
    """
    presented = _read_refresh_cookie(request)
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    new_refresh, user = await rotate_refresh_token(db, presented, _ua(request))
    set_refresh_cookie(response, new_refresh)
    return AccessTokenResponse(access_token=create_access_token(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the caller's current refresh token and clear the cookie.
    Deliberately doesn't require an access token — a user with an
    expired JWT should still be able to log out cleanly, and the
    refresh cookie itself is the credential we care about here."""
    presented = _read_refresh_cookie(request)
    await revoke_refresh_token(db, presented)
    clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Nuke every live refresh token for the authenticated user.
    Everywhere they're signed in — phones, other browsers — gets booted
    on the next access-token expiry. The current caller is included so
    we also clear its cookie."""
    await revoke_all_user_refresh_tokens(db, user.id)
    clear_refresh_cookie(response)


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionInfo]:
    """List the user's currently live sessions — powers the account
    settings 'signed-in devices' surface. Filters to non-revoked,
    non-expired rows and marks the row belonging to the caller's
    current refresh cookie so the UI can label it 'this device'."""
    from datetime import datetime

    now = datetime.utcnow()
    rows = (
        (
            await db.execute(
                select(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
                .order_by(RefreshToken.last_used_at.desc().nullslast())
            )
        )
        .scalars()
        .all()
    )

    presented = _read_refresh_cookie(request)
    current_hash = hash_refresh_token(presented) if presented else None

    return [
        SessionInfo(
            id=r.id,
            device_label=r.device_label,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
            expires_at=r.expires_at,
            is_current=(current_hash is not None and r.token_hash == current_hash),
        )
        for r in rows
    ]


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete the user's account and all owned data.

    Required by KR 개인정보보호법 / GDPR Article 17. CollectionItem +
    WishlistItem have ON DELETE CASCADE on user_id so they go with the
    user row. Portfolio snapshots also cascade. Share tokens become
    permanently dead immediately - any cached link returns 404. Refresh
    tokens cascade too so the account can't be resurrected via a stale
    cookie.

    This is irreversible. We don't soft-delete because that pattern
    invites accidental re-surfacing of "deleted" data later.
    """
    await db.delete(user)
    await db.commit()
    clear_refresh_cookie(response)
