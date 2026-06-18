"""Postgres fixed-window rate limiting as FastAPI dependencies.

One atomic upsert per request increments a per-(key, minute) counter and returns
the running count; if it exceeds the tier budget we reject with 429. Shared
across workers because the counter lives in Postgres (no Redis). Fixed-window
means up to ~2x the budget can slip through across a window boundary — an
accepted simplicity tradeoff (see 0002_api.sql).

decide() and seconds_until_* are pure so the limit logic tests without a DB.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status

from ..config import settings
from .auth import AuthContext, get_api_client
from .db import get_writable
from .limits import limit_for_tier


def decide(count: int, limit: int) -> bool:
    """Whether a request that brought the window count to `count` is allowed."""
    return count <= limit


def seconds_until_window_reset(now: datetime) -> int:
    """Seconds until the start of the next minute (for Retry-After)."""
    return 60 - now.second


def seconds_until_hour_reset(now: datetime) -> int:
    """Seconds until the start of the next hour (signup limiter Retry-After)."""
    return 3600 - (now.minute * 60 + now.second)


def rate_limit(
    response: Response,
    auth: AuthContext = Depends(get_api_client),
    conn: Any = Depends(get_writable),
) -> AuthContext:
    """Per-tier per-minute limit. Also refreshes the key's last_used_at."""
    limit = limit_for_tier(auth.tier)
    row = conn.execute(
        """
        insert into api_rate_counters (key_id, window_start, count)
        values (%s, date_trunc('minute', now()), 1)
        on conflict (key_id, window_start)
        do update set count = api_rate_counters.count + 1
        returning count, now() as now
        """,
        (auth.key_id,),
    ).fetchone()
    conn.execute("update api_keys set last_used_at = now() where id = %s", (auth.key_id,))

    count, now = int(row["count"]), row["now"]
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
    if not decide(count, limit):
        retry = seconds_until_window_reset(now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit}/min for tier '{auth.tier}').",
            headers={"Retry-After": str(retry)},
        )
    return auth


def signup_rate_limit(request: Request, conn: Any = Depends(get_writable)) -> None:
    """Per-IP per-hour limit on the unauthenticated signup endpoint."""
    ip = request.client.host if request.client else "unknown"
    limit = settings.api_signup_per_hour
    row = conn.execute(
        """
        insert into api_signup_counters (ip, window_start, count)
        values (%s, date_trunc('hour', now()), 1)
        on conflict (ip, window_start)
        do update set count = api_signup_counters.count + 1
        returning count, now() as now
        """,
        (ip,),
    ).fetchone()
    if not decide(int(row["count"]), limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signups from this IP. Try again later.",
            headers={"Retry-After": str(seconds_until_hour_reset(row["now"]))},
        )
