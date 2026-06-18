"""Runtime configuration loaded from environment / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class Settings(BaseSettings):
    """Process-wide settings. Reads from environment and a local .env file."""

    # .env.local overrides .env (put real credentials there; both are gitignored).
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore"
    )

    # Database (required only for DB-backed runs; --dry-run does not need it).
    supabase_db_url: str = ""

    # Scraper tuning.
    scrape_headless: bool = True
    scrape_delay_seconds: float = 3.0  # FBref/Sports-Ref ask for <= ~10 req/min
    scrape_timeout_ms: int = 30_000
    scrape_user_agent: str = ""

    # Anti-bot: FBref is behind Cloudflare. Using the real Chrome channel with
    # patchright clears the challenge from a normal (residential) network.
    scrape_browser_channel: str = "chrome"  # "" to use bundled Chromium instead
    scrape_challenge_wait_ms: int = 25_000  # auto-wait for a Cloudflare interstitial

    # FBref's Cloudflare Turnstile rejects ANY Playwright-launched browser. The
    # working path is to attach over the DevTools protocol to a real Chrome that
    # you launched yourself (`world-cup browser`), which Turnstile treats as a
    # genuine browser. Set this to that Chrome's CDP endpoint to use it.
    scrape_cdp_url: str = ""  # e.g. http://localhost:9222
    scrape_user_data_dir: str = ".cache/cdp-chrome"  # dedicated profile for that Chrome

    # --- API server ---------------------------------------------------------
    # Optional separate DSN for the read path (defaults to supabase_db_url). Lets
    # you point reads at a read replica / different pooler than the scraper writes.
    api_read_only_db_url: str = ""
    # psycopg_pool sizes. workers * api_pool_max must stay under Supabase's
    # connection ceiling — prefer the Supabase session pooler DSN for the API.
    api_pool_min: int = 2
    api_pool_max: int = 10
    # Per-minute request budgets by client tier (see api/limits.py).
    api_rate_free: int = 60
    api_rate_premium: int = 600
    # Unverified clients (no email verification yet) are capped hard, regardless
    # of tier: a low request rate and a small max page size.
    api_rate_unverified: int = 10
    api_max_page: int = 200            # verified ceiling on rows per call
    api_max_page_unverified: int = 25  # unverified ceiling on rows per call
    # Default lifetime (days) of a freshly issued key.
    api_key_ttl_days: int = 30
    # Signups allowed per client IP per hour (abuse guard on the public endpoint).
    api_signup_per_hour: int = 5

    @property
    def user_agent(self) -> str:
        return self.scrape_user_agent or DEFAULT_USER_AGENT

    def read_only_db_url(self) -> str:
        """DSN for the API read path: api_read_only_db_url if set, else the main one."""
        return self.api_read_only_db_url or self.require_db_url()

    def require_db_url(self) -> str:
        if not self.supabase_db_url:
            raise RuntimeError(
                "SUPABASE_DB_URL is not set. Add it to .env (see .env.example) "
                "or run with --dry-run to skip the database."
            )
        return self.supabase_db_url


settings = Settings()
