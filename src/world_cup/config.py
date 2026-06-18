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

    @property
    def user_agent(self) -> str:
        return self.scrape_user_agent or DEFAULT_USER_AGENT

    def require_db_url(self) -> str:
        if not self.supabase_db_url:
            raise RuntimeError(
                "SUPABASE_DB_URL is not set. Add it to .env (see .env.example) "
                "or run with --dry-run to skip the database."
            )
        return self.supabase_db_url


settings = Settings()
