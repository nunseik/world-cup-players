"""Shared fixtures for API tests.

The repo's tests are offline and DB-free. We keep that here by overriding the
FastAPI DB dependencies with in-memory fake connections that route SQL by table
keyword and return canned rows. No Postgres, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from world_cup.api import db as api_db
from world_cup.api.app import create_app


class FakeResult:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.rowcount = len(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeConn:
    """Routes execute() to a callable that maps (sql, params) -> list[dict]."""

    def __init__(self, router):
        self._router = router
        self.calls: list[tuple] = []

    def execute(self, sql: str, params: tuple = ()):  # noqa: D401
        self.calls.append((sql, params))
        rows = self._router(sql, params)
        return FakeResult(rows)


@dataclass
class FakeState:
    """Knobs tests flip to steer the fake DB."""

    key_valid: bool = True
    tier: str = "free"
    verified: bool = True                    # default: a verified client (lifts unverified caps)
    rate_count: int = 1                      # value the counter upsert "returns"
    signup_count: int = 1                    # value the signup counter "returns"
    tournaments: list = field(default_factory=list)


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=10)


def _read_router(state: FakeState):
    def route(sql: str, params: tuple) -> list[dict]:
        s = sql.lower()
        if "from api_keys" in s and "key_hash" in s:
            if not state.key_valid:
                return []
            return [{
                "key_id": 1, "expires_at": _future(), "revoked_at": None,
                "client_id": 1, "tier": state.tier, "is_active": True,
                "is_verified": state.verified,
            }]
        if "count(" in s:
            return [{"count": len(state.tournaments) if "tournaments" in s else 0}]
        if "from tournaments where year" in s:
            year = params[0]
            return [t for t in state.tournaments if t["year"] == year][:1]
        if "from tournaments" in s:
            return list(state.tournaments)
        if "from player_tournament_stats" in s or "leaderboard" in s:
            return []
        return []
    return route


def _write_router(state: FakeState):
    def route(sql: str, params: tuple) -> list[dict]:
        s = sql.lower()
        if "api_rate_counters" in s:
            return [{"count": state.rate_count, "now": datetime.now(timezone.utc)}]
        if "api_signup_counters" in s:
            return [{"count": state.signup_count, "now": datetime.now(timezone.utc)}]
        if "insert into api_clients" in s:
            return [{"id": 1}]
        if "insert into api_keys" in s or "update api_keys" in s:
            return []
        return []
    return route


@pytest.fixture
def state() -> FakeState:
    return FakeState(tournaments=[
        {"year": 2022, "host_country": "Qatar", "start_date": None,
         "end_date": None, "num_teams": 32},
    ])


@pytest.fixture
def client(state: FakeState):
    app = create_app()
    read_conn = FakeConn(_read_router(state))
    write_conn = FakeConn(_write_router(state))
    app.dependency_overrides[api_db.get_conn] = lambda: read_conn
    app.dependency_overrides[api_db.get_writable] = lambda: write_conn
    # Do NOT use TestClient as a context manager: that runs the lifespan, which
    # opens real DB pools. Plain construction skips startup, and the DB
    # dependencies are fully overridden above anyway.
    return TestClient(app)
