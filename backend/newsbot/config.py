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
    # 5 / day is the friends-beta cadence — matches what active
    # Pokémon TCG communities post (3-4 drop alerts + 1-2 editorial)
    # without overwhelming a small reader list. Each post averages
    # ~$0.012 (Sonnet 4.6 medium), so 5/day ≈ $1.80/month.
    daily_post_limit: int = 5
    dry_run: bool = False
    # Bot's by-line on the public post. Override via env to change it.
    bot_author_name: str = "PullList Bot"
    # When True, skip Tavily entirely. We don't have a Tavily key
    # provisioned and friends-beta doesn't justify a second-pass
    # cost gate — LO reviews every draft before publishing anyway.
    # Flipped on to silence the "api_key_set=False" warning that
    # otherwise fires for every item every run.
    skip_factcheck: bool = True

    # ── Market-report source (Phase B Sprint 1) ──
    # Off by default. Only the weekly Monday cron flips this on;
    # the daily news bot keeps its regular shape.
    market_report_enabled: bool = False

    # ── Set-overview source (Phase B Sprint 2) ──
    # Off by default. Its own daily workflow flips it on and does
    # nothing on days with no fresh set release.
    set_overview_enabled: bool = False

    # ── Price-club source (Phase B Sprint 3) ──
    # Off by default. Monthly workflow (1st of the month) flips it on.
    price_club_enabled: bool = False

    # ── Illustrator-feature source (Phase B Sprint 4) ──
    # Off by default. Auto-rotates on the top artist among chase-tier
    # cards each fire; override via ILLUSTRATOR_FEATURE_ARTIST=<name>
    # to force a specific pick for that run.
    illustrator_feature_enabled: bool = False
    illustrator_feature_artist: str = ""

    # ── Web-search source (Phase 2 Track A) ──
    # Off by default while we tune query design and domain allowlist.
    # Flip via WEB_SEARCH_ENABLED=1 env (e.g. in workflow inputs).
    web_search_enabled: bool = False
    # Pydantic-settings parses JSON list from env var. Examples:
    #   WEB_SEARCH_QUERIES='["Pokemon TCG preorder 2026"]'
    web_search_queries: list[str] = Field(
        default_factory=lambda: [
            # Editorial / general — PokeBeach / Pokemon.com / Bulbapedia
            # tend to win these.
            "Pokemon TCG new set release 2026",
            "Pokemon TCG preorder drop 2026",
            "Pokemon Center exclusive release 2026",
            # Retailer-named — without the retailer in the query,
            # Google /news surfaces generic round-up blogs instead
            # of the actual SKU page. Naming the retailer pulls the
            # deal post itself.
            "Pokemon TCG Sam's Club exclusive bundle",
            "Pokemon TCG Costco bundle release",
            "Pokemon TCG Walmart exclusive set",
            "Pokemon TCG Best Buy preorder",
            "Pokemon TCG GameStop preorder",
        ]
    )
    web_search_days_back: int = 3
    # 10 / query gives the topic + domain filters more raw material
    # to chew through — most queries get filtered down hard by the
    # retailer / topic gates so a tight 5 was leaving real drops on
    # the table. Serper free tier is 2500 credits/month; 7 queries
    # × 30 days = 210/month, well under cap.
    web_search_max_per_query: int = 10
    # Hosts (substring match) we trust enough to scrape + summarize.
    # Other hosts surface in results are ignored. Conservative initial
    # set — broaden once we see real result quality.
    web_search_allowed_domains: list[str] = Field(
        default_factory=lambda: [
            # Pokemon-exclusive publishers — bypass topic filter via
            # web_search_trusted_domains below.
            "pokemon.com",
            "pokemoncenter.com",
            "pokebeach.com",
            "bulbagarden.net",
            "pokemonmillennium.net",
            "bleedingcool.com",
            # Big-box retailers — these stock more than Pokemon so
            # the topic filter (must contain "pokemon") fires here.
            # Catches Sam's Club / Costco / Walmart / Target / Best
            # Buy exclusives that editorial sites rarely cover.
            "samsclub.com",
            "costco.com",
            "walmart.com",
            "target.com",
            "bestbuy.com",
            "tcgplayer.com",
            "gamestop.com",
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
