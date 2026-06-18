"""Endpoint wiring tests via TestClient with fake DB dependencies.

Covers auth (401/200), per-tier rate limiting (429 + Retry-After), pagination
envelope, and 404 handling — all offline.
"""

from __future__ import annotations

HEADERS = {"X-API-Key": "wc_testtoken"}


def test_health_needs_no_auth(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_missing_key_is_401(client):
    assert client.get("/v1/tournaments").status_code == 401


def test_bad_key_is_401(client, state):
    state.key_valid = False
    assert client.get("/v1/tournaments", headers=HEADERS).status_code == 401


def test_bearer_token_accepted(client):
    r = client.get("/v1/tournaments", headers={"Authorization": "Bearer wc_testtoken"})
    assert r.status_code == 200


def test_tournaments_list_envelope(client):
    r = client.get("/v1/tournaments", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["year"] == 2022
    assert {"items", "total", "limit", "offset"} <= body.keys()


def test_tournament_404(client, state):
    r = client.get("/v1/tournaments/1930", headers=HEADERS)
    assert r.status_code == 404


def test_rate_limit_headers_present(client, state):
    state.rate_count = 5
    r = client.get("/v1/tournaments", headers=HEADERS)
    assert r.headers["X-RateLimit-Limit"] == "60"
    assert r.headers["X-RateLimit-Remaining"] == "55"


def test_free_tier_429_over_limit(client, state):
    state.tier = "free"
    state.rate_count = 61  # 61st request in the window
    r = client.get("/v1/tournaments", headers=HEADERS)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_premium_tier_allows_more(client, state):
    state.tier = "premium"
    state.rate_count = 61  # fine for premium (limit 600)
    r = client.get("/v1/tournaments", headers=HEADERS)
    assert r.status_code == 200
