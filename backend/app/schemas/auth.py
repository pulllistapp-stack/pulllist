from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)
    # Honeypot — frontend renders a hidden input named `website` and
    # bots that auto-fill every form input will trip this. Humans never
    # see it, so it should always come through empty.
    website: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    # ID token (JWT) returned by Google Identity Services on the frontend
    # after the user authorizes our app. We verify the signature server-side
    # so the frontend can't forge identities.
    credential: str = Field(min_length=20)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class AccessTokenResponse(BaseModel):
    """Slimmed-down /auth/refresh response — the browser already has the
    user object cached from login, no need to re-ship it every 15 minutes."""

    access_token: str
    token_type: str = "bearer"


class SessionInfo(BaseModel):
    """One active refresh-token row surfaced on /auth/sessions."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    device_label: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime
    is_current: bool = False
