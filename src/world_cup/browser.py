"""Browser wrapper: attaches to a real Chrome (CDP) or launches one.

FBref's Cloudflare Turnstile rejects any Playwright/patchright-launched browser
(it loops forever and never issues a clearance token — a human can't solve it
there either). The reliable path is to drive a Chrome **you** launched, over the
DevTools protocol: such a browser isn't automation-fingerprinted, so Turnstile
validates normally and we just read the already-cleared pages.

Modes:
- **CDP attach** (``SCRAPE_CDP_URL`` set): connect to your running Chrome via a
  minimal raw-CDP client (see ``_CDPClient``). Used for FBref. We never close
  your browser.
- **Launch** (default): patchright launches a browser. Fine for non-Cloudflare
  sites like ESPN.

Why a hand-rolled CDP client instead of ``connect_over_cdp``: patchright's
connect handshake issues a browser-level ``Browser.setDownloadBehavior`` that
Chrome 149+ rejects with *"Browser context management is not supported"*,
aborting the attach before any page loads. The scraper only needs ``get_html``,
so we speak CDP protocol 1.3 directly — which is stable across Chrome versions.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from pathlib import Path
from types import TracebackType

import structlog
import websockets

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


class CDPError(RuntimeError):
    """A CDP command returned an error response."""


class _CDPClient:
    """Minimal Chrome DevTools Protocol client over a single WebSocket.

    Connects to the *browser*-level endpoint of a user-launched Chrome and drives
    one page at a time with flattened sessions. Commands are issued one-at-a-time
    (request/response); protocol events are read and skipped. Deliberately tiny —
    it implements only what ``get_html`` needs, and avoids patchright's connect
    handshake which Chrome 149+ rejects.
    """

    def __init__(self, http_url: str) -> None:
        self._http_url = http_url.rstrip("/")
        self._ws: websockets.ClientConnection | None = None
        self._next_id = 0

    async def connect(self) -> None:
        ws_url = await asyncio.to_thread(self._discover_ws_url)
        log.info("cdp.connect", url=self._http_url)
        # max_size=None: FBref stat pages routinely exceed the 1 MiB default frame cap.
        self._ws = await websockets.connect(ws_url, max_size=None)

    def _discover_ws_url(self) -> str:
        with urllib.request.urlopen(f"{self._http_url}/json/version", timeout=10) as resp:
            data = json.load(resp)
        url = data.get("webSocketDebuggerUrl")
        if not url:
            raise CDPError(f"No webSocketDebuggerUrl at {self._http_url}/json/version")
        return url

    async def close(self) -> None:
        # Close only our WebSocket — never the user's browser.
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def _cmd(self, method: str, params: dict | None = None, session_id: str | None = None) -> dict:
        assert self._ws is not None, "CDP client is not connected"
        self._next_id += 1
        msg_id = self._next_id
        payload: dict = {"id": msg_id, "method": method, "params": params or {}}
        if session_id:
            payload["sessionId"] = session_id
        await self._ws.send(json.dumps(payload))
        timeout = settings.scrape_timeout_ms / 1000
        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            data = json.loads(raw)
            if data.get("id") != msg_id:
                continue  # an event or another command's reply — skip
            if "error" in data:
                raise CDPError(f"{method}: {data['error'].get('message', data['error'])}")
            return data.get("result", {})

    async def _eval(self, session_id: str, expression: str) -> object:
        result = await self._cmd(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
            session_id,
        )
        return result.get("result", {}).get("value")

    async def _wait_out_challenge(self, session_id: str) -> str:
        """Poll the page title until a Cloudflare interstitial clears, or raise."""
        deadline = settings.scrape_challenge_wait_ms / 1000
        waited = 0.0
        while True:
            title = str(await self._eval(session_id, "document.title") or "").lower()
            if not any(m in title for m in _CHALLENGE_MARKERS):
                return title
            if waited >= deadline:
                raise ChallengeBlocked(
                    f"Cloudflare challenge did not clear within {deadline:.0f}s. "
                    "Launch your own Chrome with `world-cup browser`, clear FBref once, "
                    "then scrape with `--cdp`."
                )
            await asyncio.sleep(2)
            waited += 2

    async def get_html(self, url: str, *, wait_for: str | None = None) -> str:
        """Navigate to ``url`` in a fresh tab, clear Cloudflare, return the DOM HTML."""
        target = await self._cmd("Target.createTarget", {"url": "about:blank"})
        target_id = target["targetId"]
        attach = await self._cmd("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = attach["sessionId"]
        try:
            await self._cmd("Page.enable", session_id=session_id)
            log.info("navigate", url=url)
            await self._cmd("Page.navigate", {"url": url}, session_id)
            await self._wait_out_challenge(session_id)
            await self._poll(session_id, "document.readyState === 'complete'")
            if wait_for:
                await self._poll(session_id, f"!!document.querySelector({json.dumps(wait_for)})")
            html = await self._eval(session_id, "document.documentElement.outerHTML")
        finally:
            await self._cmd("Target.closeTarget", {"targetId": target_id})
        await asyncio.sleep(settings.scrape_delay_seconds)
        return str(html)

    async def _poll(self, session_id: str, js_condition: str) -> None:
        """Evaluate ``js_condition`` until truthy or the navigation timeout elapses."""
        deadline = settings.scrape_timeout_ms / 1000
        waited = 0.0
        while not await self._eval(session_id, js_condition):
            if waited >= deadline:
                raise CDPError(f"Timed out waiting for: {js_condition}")
            await asyncio.sleep(0.5)
            waited += 0.5


class Browser:
    """Async context manager over a Chrome context (CDP-attached or launched)."""

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: PWBrowser | None = None
        self._context: BrowserContext | None = None
        self._cdp: _CDPClient | None = None  # set when attached to a user's Chrome
        self._attached = False  # True when we connected to a user's Chrome via CDP

    async def __aenter__(self) -> "Browser":
        if settings.scrape_cdp_url:
            await self._attach_cdp()
        else:
            self._pw = await async_playwright().start()
            await self._launch()
        return self

    async def _attach_cdp(self) -> None:
        # Raw CDP — bypasses patchright's connect handshake (rejected by Chrome 149+).
        self._cdp = _CDPClient(settings.scrape_cdp_url)
        await self._cdp.connect()
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
        # Chrome won't start inside a VM/container without a user namespace unless
        # --no-sandbox is passed. Safe here: the browser only scrapes public pages.
        if sys.platform == "linux":
            kwargs["args"] = ["--no-sandbox", "--disable-dev-shm-usage"]
        self._context = await self._pw.chromium.launch_persistent_context(**kwargs)
        await self._context.route("**/*", self._maybe_block)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Never close a browser we attached to — it belongs to the user.
        if self._cdp is not None:
            await self._cdp.close()
        elif not self._attached and self._context:
            await self._context.close()
        if self._pw:
            await self._pw.stop()

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser must be used as a context manager (launched mode).")
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
        if self._cdp is not None:
            return await self._cdp.get_html(url, wait_for=wait_for)

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
