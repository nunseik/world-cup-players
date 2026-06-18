"""Unverified clients get a lower rate cap and smaller page sizes.

Pure-decision tests plus endpoint tests (TestClient + fake DB). Verified vs
unverified is driven by the `state.verified` knob in conftest.
"""

from __future__ import annotations

from world_cup.api.limits import effective_rate_limit, max_page_size

HEADERS = {"X-API-Key": "wc_testtoken"}


# --- pure helpers -----------------------------------------------------------


def test_unverified_rate_is_capped_regardless_of_tier():
    # premium would be 600, but unverified caps to 10
    assert effective_rate_limit("premium", is_verified=False) == 10
    assert effective_rate_limit("premium", is_verified=True) == 600
    # free (60) is also capped down to 10 when unverified
    assert effective_rate_limit("free", is_verified=False) == 10
    assert effective_rate_limit("free", is_verified=True) == 60


def test_unverified_page_size_is_smaller():
    assert max_page_size(is_verified=False) == 25
    assert max_page_size(is_verified=True) == 200


# --- endpoint behavior ------------------------------------------------------


def test_unverified_rate_limit_header_is_low(client, state):
    state.verified = False
    state.rate_count = 5
    r = client.get("/v1/tournaments", headers=HEADERS)
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "10"


def test_unverified_429_past_low_cap(client, state):
    state.verified = False
    state.rate_count = 11  # 11th request, cap is 10
    r = client.get("/v1/tournaments", headers=HEADERS)
    assert r.status_code == 429


def test_unverified_page_size_clamped(client, state):
    state.verified = False
    r = client.get("/v1/tournaments?limit=100", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["limit"] == 25  # clamped down from 100


def test_verified_page_size_allowed(client, state):
    state.verified = True
    r = client.get("/v1/tournaments?limit=100", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["limit"] == 100  # under the verified ceiling (200)
