"""Pure tests for the raw CDP client's protocol handling (no network/browser).

A scripted fake WebSocket stands in for Chrome: it inspects each command we send
and queues a canned reply, letting us exercise id-matching, event-skipping, error
propagation, and the full get_html navigation flow deterministically.

Tests are driven with ``asyncio.run`` so we need no async pytest plugin.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from world_cup.browser import CDPError, ChallengeBlocked, _CDPClient


class FakeWS:
    """Minimal stand-in for a websockets connection driven by a reply script.

    ``responder`` maps a sent CDP message (dict) to either a single reply dict or
    a list of dicts (e.g. an event followed by the real reply) to be recv'd next.
    """

    def __init__(self, responder):
        self._responder = responder
        self._inbox: list[dict] = []
        self.closed = False

    async def send(self, raw: str) -> None:
        msg = json.loads(raw)
        reply = self._responder(msg)
        if isinstance(reply, list):
            self._inbox.extend(reply)
        elif reply is not None:
            self._inbox.append(reply)

    async def recv(self) -> str:
        return json.dumps(self._inbox.pop(0))

    async def close(self) -> None:
        self.closed = True


def _client(responder) -> _CDPClient:
    c = _CDPClient("http://localhost:9222")
    c._ws = FakeWS(responder)
    return c


def test_cmd_matches_id_and_skips_events():
    def responder(msg):
        # An unrelated event arrives before the matching reply — must be skipped.
        return [
            {"method": "Page.frameNavigated", "params": {}},
            {"id": msg["id"], "result": {"ok": True}},
        ]

    c = _client(responder)
    assert asyncio.run(c._cmd("Page.enable")) == {"ok": True}


def test_cmd_raises_on_error_response():
    def responder(msg):
        return {"id": msg["id"], "error": {"message": "Browser context management is not supported"}}

    c = _client(responder)
    with pytest.raises(CDPError, match="not supported"):
        asyncio.run(c._cmd("Browser.setDownloadBehavior"))


def test_get_html_happy_path():
    page_html = "<html><body><table id='stats'></table></body></html>"

    def responder(msg):
        method, mid = msg["method"], msg["id"]
        if method == "Target.createTarget":
            return {"id": mid, "result": {"targetId": "T1"}}
        if method == "Target.attachToTarget":
            return {"id": mid, "result": {"sessionId": "S1"}}
        if method == "Runtime.evaluate":
            expr = msg["params"]["expression"]
            if "document.title" in expr:
                value = "World Cup 2022 Stats"  # not a challenge title
            elif "readyState" in expr:
                value = True
            elif "querySelector" in expr:
                value = True
            elif "outerHTML" in expr:
                value = page_html
            else:
                value = None
            return {"id": mid, "result": {"result": {"value": value}}}
        # Page.enable, Page.navigate, Target.closeTarget
        return {"id": mid, "result": {}}

    c = _client(responder)
    html = asyncio.run(c.get_html("https://fbref.com/x", wait_for="table"))
    assert html == page_html


def test_get_html_raises_when_challenge_never_clears(monkeypatch):
    # Keep the test fast: tiny challenge window and no real sleeping.
    from world_cup import browser as browser_mod

    monkeypatch.setattr(browser_mod.settings, "scrape_challenge_wait_ms", 0)

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(browser_mod.asyncio, "sleep", _no_sleep)

    def responder(msg):
        method, mid = msg["method"], msg["id"]
        if method == "Target.createTarget":
            return {"id": mid, "result": {"targetId": "T1"}}
        if method == "Target.attachToTarget":
            return {"id": mid, "result": {"sessionId": "S1"}}
        if method == "Runtime.evaluate":
            # Title is stuck on the Cloudflare interstitial forever.
            return {"id": mid, "result": {"result": {"value": "Just a moment..."}}}
        return {"id": mid, "result": {}}

    c = _client(responder)
    with pytest.raises(ChallengeBlocked):
        asyncio.run(c.get_html("https://fbref.com/x"))
