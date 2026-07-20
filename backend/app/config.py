from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./pulllist.db"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    pokemontcg_api_key: str = ""

    # Auth — override in .env, especially in production.
    #
    # Two-token model: short-lived access JWT (Bearer header, localStorage)
    # + long-lived opaque refresh token (httpOnly cookie, sha256-hashed in
    # DB). Access expiry stays tight so a stolen JWT dies fast; refresh
    # expiry is what actually keeps a user signed in.
    jwt_secret: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 60
    refresh_cookie_name: str = "pulllist_refresh"

    # Google Identity Services - same Client ID the frontend uses. We
    # verify ID tokens against Google's public keys + assert this audience
    # so tokens issued for another app can't authenticate against us.
    google_client_id: str = ""

    # Google Gemini API key — an A/B alternative to Anthropic Claude
    # for card scanning. Gemini 2.0 Flash reads cards at the same
    # quality as Haiku 4.5 but ~30x cheaper. If empty, the
    # /cards/scan-gemini endpoint returns 501 so testing gracefully
    # falls back.
    gemini_api_key: str = ""

    # Which Gemini model to hit. `gemini-2.5-flash-lite` is the safest
    # default: real free-tier quota (1000 RPD) without needing to
    # enable billing on the Google Cloud project, and card OCR
    # quality is fine. `gemini-1.5-flash` was retired from the v1beta
    # endpoint; `gemini-2.0-flash` gates its free tier behind
    # billing-enabled (returns 429 quota-0 otherwise). Once billing
    # is on, override via GEMINI_MODEL env var to a bigger model.
    gemini_model: str = "gemini-2.5-flash-lite"

    # Cloudflare R2 (S3-compatible object storage). Used for large
    # binary artifacts that would bloat the Neon Postgres free tier —
    # currently: catalog card image mirror + the CNN embedding index
    # for on-device bulk scan (Phase 3). The bucket name defaults to
    # the existing one from the KR set-logos backup so we share
    # infrastructure instead of provisioning a second bucket.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_embeddings: str = "pulllist-setslogosbackup"

    @property
    def r2_endpoint(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
        )

    env: str = "development"
    debug: bool = True

    # eBay Browse API (client_credentials flow — no eBay user data stored)
    ebay_env: str = "sandbox"  # "sandbox" or "production"
    ebay_app_id: str = ""
    ebay_cert_id: str = ""
    ebay_sandbox_app_id: str = ""
    ebay_sandbox_cert_id: str = ""
    ebay_marketplace_id: str = "EBAY_US"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ebay_active_app_id(self) -> str:
        return self.ebay_sandbox_app_id if self.ebay_env == "sandbox" else self.ebay_app_id

    @property
    def ebay_active_cert_id(self) -> str:
        return self.ebay_sandbox_cert_id if self.ebay_env == "sandbox" else self.ebay_cert_id

    @property
    def ebay_base_url(self) -> str:
        return (
            "https://api.sandbox.ebay.com"
            if self.ebay_env == "sandbox"
            else "https://api.ebay.com"
        )


settings = Settings()
