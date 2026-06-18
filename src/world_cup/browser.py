"""Browser wrapper: attaches to a real Chrome (CDP) or launches one.

FBref's Cloudflare Turnstile rejects any Playwright/patchright-launched browser
(it loops forever and never issues a clearance token — a human can't solve it
there either). The reliable path is to drive a Chrome **you** launched, over the
DevTools protocol: such a browser isn't automation-fingerprinted, so Turnstile
validates normally and we just read the already-cleared pages.

Modes:
- **CDP attach** (``SCRAPE_CDP_URL`` set): connect to your running Chrome. Used
  for FBref. We never close your browser.
- **Launch** (default): patchright launches a browser. Fine for non-Cloudflare
  sites like ESPN.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import TracebackType

import structlog

# patchright exposes the same async API as playwright.
from patchright.async_api import Browser as PWBrowser, BrowserContext, Page, Playwright, async_playwright
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings

log = structlog.get_logger(__name__)

# Resource types we never need for scraping stat tables — blocked for speed.
_BLOCKED_RESOURCES = {"image", "media", "font"}

# Title shown by Cloudflare's managed-challenge interstitial.
_CHALLENGE_MARKERS = ("just a moment", "attention required", "checking your browser")


class ChallengeBlocked(RuntimeError):
    """Raised when a Cloudflare challenge never clears within the wait window."""


class Browser:
    """Async context manager over a Chrome context (CDP-attached or launched)."""

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: PWBrowser | None = None
        self._context: BrowserContext | None = None
        self._attached = False  # True when we connected to a user's Chrome via CDP

    async def __aenter__(self) -> "Browser":
        self._pw = await async_playwright().start()
        if settings.scrape_cdp_url:
            await self._attach_cdp()
        else:
            await self._launch()
        return self

    async def _attach_cdp(self) -> None:
        assert self._pw is not None
        log.info("cdp.connect", url=settings.scrape_cdp_url)
        self._browser = await self._pw.chromium.connect_over_cdp(settings.scrape_cdp_url)
        # Reuse the real browser's existing context (carries the CF clearance).
        contexts = self._browser.contexts
        self._context = contexts[0] if contexts else await self._browser.new_context()
        self._attached = True

    async def _launch(self) -> None:
        assert self._pw is not None
        Path(settings.scrape_user_data_dir).mkdir(parents=True, exist_ok=True)
        kwargs: dict = {
            "user_data_dir": settings.scrape_user_data_dir,
            "headless": settings.scrape_headless,
            "viewport": {"width": 1280, "height": 900},
            "locale": "en-US",
        }
        if settings.scrape_browser_channel:
            kwargs["channel"] = settings.scrape_browser_channel
        if settings.scrape_user_agent:
            kwargs["user_agent"] = settings.scrape_user_agent
        self._context = await self._pw.chromium.launch_persistent_context(**kwargs)
        await self._context.route("**/*", self._maybe_block)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Never close a browser we attached to — it belongs to the user.
        if not self._attached and self._context:
            await self._context.close()
        if self._pw:
            await self._pw.stop()

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser must be used as a context manager.")
        return self._context

    @staticmethod
    async def _maybe_block(route) -> None:  # noqa: ANN001 - Route
        if route.request.resource_type in _BLOCKED_RESOURCES:
            await route.abort()
        else:
            await route.continue_()

    async def _wait_out_challenge(self, page: Page) -> None:
        """Poll until a Cloudflare interstitial clears, or raise ChallengeBlocked."""
        deadline = settings.scrape_challenge_wait_ms / 1000
        waited = 0.0
        while waited < deadline:
            title = (await page.title()).lower()
            if not any(m in title for m in _CHALLENGE_MARKERS):
                return
            await asyncio.sleep(2)
            waited += 2
        raise ChallengeBlocked(
            f"Cloudflare challenge did not clear within {deadline:.0f}s (URL: {page.url}). "
            "Launch your own Chrome with `world-cup browser`, clear FBref once, then "
            "scrape with `--cdp`."
        )

    @retry(
        retry=retry_if_exception_type(Exception) & retry_if_not_exception_type(ChallengeBlocked),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    )
    async def get_html(self, url: str, *, wait_for: str | None = None) -> str:
        """Navigate, clear any Cloudflare challenge, optionally wait for a selector."""
        page: Page = await self.context.new_page()
        try:
            log.info("navigate", url=url)
            await page.goto(url, timeout=settings.scrape_timeout_ms, wait_until="domcontentloaded")
            await self._wait_out_challenge(page)
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=settings.scrape_timeout_ms)
            html = await page.content()
        finally:
            if not page.is_closed():
                await page.close()
        await asyncio.sleep(settings.scrape_delay_seconds)
        return html
