"""Signup endpoint: issues a key, validates email, enforces the per-IP limit."""

from __future__ import annotations


def test_signup_returns_key(client, state):
    r = client.post("/v1/signup", json={"email": "Me@Example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["api_key"].startswith("wc_")
    assert body["tier"] == "free"
    assert "expires_at" in body


def test_signup_rejects_bad_email(client):
    r = client.post("/v1/signup", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_signup_rate_limited_by_ip(client, state):
    state.signup_count = 99  # over api_signup_per_hour (5)
    r = client.post("/v1/signup", json={"email": "me@example.com"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
