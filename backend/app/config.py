from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./pulllist.db"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    pokemontcg_api_key: str = ""

    # Auth — override in .env, especially in production
    jwt_secret: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 14  # 14 days

    # Google Identity Services - same Client ID the frontend uses. We
    # verify ID tokens against Google's public keys + assert this audience
    # so tokens issued for another app can't authenticate against us.
    google_client_id: str = ""

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
