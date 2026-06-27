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
    # Cost-optimised default: Sonnet 4.6 at medium effort. News
    # rewriting is well within Sonnet's range; Opus's extra capability
    # mostly buys nothing for 400-word summaries. Empirically:
    #   claude-sonnet-4-6 / medium → ~$0.012 per article (~$0.70/mo)
    #   claude-opus-4-8   / high   → ~$0.075 per article (~$4.50/mo)
    # Override via env (CLAUDE_MODEL / CLAUDE_EFFORT) when an article
    # turns out worse than expected — Opus high is the fallback ceiling.
    claude_model: str = "claude-sonnet-4-6"
    # Adaptive thinking effort level (low | medium | high | xhigh | max).
    claude_effort: str = "medium"

    # ── Tavily ── (currently used by factcheck.py; web_search now
    # uses Serper instead, see below)
    tavily_api_key: str = ""

    # ── Serper ── (web_search source, Phase 2 Track A)
    # Google-results search via google.serper.dev — free tier 2500
    # credits / month, one credit per /news call. Plenty for our
    # ~1-3 searches/day.
    serper_api_key: str = ""

    # ── Runtime knobs ──
    daily_post_limit: int = 2
    dry_run: bool = False
    # Bot's by-line on the public post. Override via env to change it.
    bot_author_name: str = "PullList Bot"
    # When True, skip Tavily entirely (useful for CI dry runs that
    # don't have a TAVILY_API_KEY secret available).
    skip_factcheck: bool = False

    # ── Web-search source (Phase 2 Track A) ──
    # Off by default while we tune query design and domain allowlist.
    # Flip via WEB_SEARCH_ENABLED=1 env (e.g. in workflow inputs).
    web_search_enabled: bool = False
    # Pydantic-settings parses JSON list from env var. Examples:
    #   WEB_SEARCH_QUERIES='["Pokemon TCG preorder 2026"]'
    web_search_queries: list[str] = Field(
        default_factory=lambda: [
            "Pokemon TCG new set release 2026",
            "Pokemon TCG preorder drop 2026",
            "Pokemon Center exclusive release 2026",
        ]
    )
    web_search_days_back: int = 3
    web_search_max_per_query: int = 5
    # Hosts (substring match) we trust enough to scrape + summarize.
    # Other hosts surface in results are ignored. Conservative initial
    # set — broaden once we see real result quality.
    web_search_allowed_domains: list[str] = Field(
        default_factory=lambda: [
            "pokemon.com",
            "pokemoncenter.com",
            "pokebeach.com",
            "bulbagarden.net",
            "bestbuy.com",
            "target.com",
            "tcgplayer.com",
            "pokemonmillennium.net",
            "bleedingcool.com",
        ]
    )
    # Lowercased keyword required in result title or snippet — any
    # match is enough. Filters out non-Pokemon TCG noise that broad
    # retailers (Target, BestBuy, TCGPlayer) surface when generic
    # "TCG preorder" queries match Flesh and Blood / Magic / MLB /
    # etc. listings. Tunable per environment via the JSON env var.
    web_search_required_keywords: list[str] = Field(
        default_factory=lambda: ["pokemon", "pokémon", "pokémon"]
    )
    # Subset of allowed_domains that are Pokemon-exclusive publishers
    # — results from these bypass the keyword filter entirely (a set
    # name or character mention in the title is enough; the domain
    # itself guarantees topic relevance). Without this, posts like
    # "Storm Emeralda" or "Pikachu Wedding Plush" get false-negatived
    # because neither title contains the literal word "Pokemon".
    web_search_trusted_domains: list[str] = Field(
        default_factory=lambda: [
            "pokemon.com",
            "pokemoncenter.com",
            "pokebeach.com",
            "bulbagarden.net",
            "pokemonmillennium.net",
        ]
    )


settings = Settings()
