"""Auth routes — signup, login, me, google."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas.auth import (
    GoogleAuthRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(
    payload: SignupRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
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

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, db: AsyncSession = Depends(get_db)
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

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.post("/google", response_model=TokenResponse)
async def google_login(
    payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)
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

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
