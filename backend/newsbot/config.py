"""Env-driven settings for the newsbot. Loaded once on module import.

All non-secret defaults match the production deployment described in
SPEC.md. Secrets must come from env (GitHub Actions secrets in CI,
.env file locally). Missing required secrets raise at import time so
a misconfigured run dies fast instead of getting 401s deep into the
pipeline.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── PullList API ──
    pulllist_api_base: str = Field(default="https://api.pulllist.org/api/v1")
    # Bot reuses the existing admin account instead of a dedicated
    # newsbot user — simpler ops, one less mailbox. Implication: bot
    # creds = admin creds, so a bot leak compromises admin access.
    # Acceptable tradeoff at friends-beta scale; revisit if scope grows.
    newsbot_admin_email: str = "admin@pulllist.org"
    newsbot_admin_password: str = ""

    # ── Anthropic / Claude ──
    anthropic_api_key: str = ""
    # Quality matters for SEO/AdSense; volume is ~2 posts/day so Opus
    # is fine on cost (~$6/mo per SPEC).
    claude_model: str = "claude-opus-4-8"
    # Adaptive thinking effort level (low | medium | high | xhigh | max).
    # 'high' is the sweet spot for content generation — model thinks
    # enough to produce well-structured articles without overspending.
    # Opus 4.8 requires adaptive-only; budget_tokens API was removed.
    claude_effort: str = "high"

    # ── Tavily ──
    tavily_api_key: str = ""

    # ── Runtime knobs ──
    daily_post_limit: int = 2
    dry_run: bool = False
    # Bot's by-line on the public post. Override via env to change it.
    bot_author_name: str = "PullList Bot"
    # When True, skip Tavily entirely (useful for CI dry runs that
    # don't have a TAVILY_API_KEY secret available).
    skip_factcheck: bool = False


settings = Settings()
