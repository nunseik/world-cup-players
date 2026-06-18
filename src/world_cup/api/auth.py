"""API-key authentication as a FastAPI dependency.

Reads the token from `X-API-Key` (canonical) or `Authorization: Bearer <token>`,
hashes it, looks up the key+client row on the read pool, and validates expiry /
revocation / active status. Bookkeeping writes (last_used_at) happen later in the
rate-limit dependency on the write pool — keeping this path read-only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from .db import get_conn
from .keys import hash_key, is_key_valid

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing API key.",
    headers={"WWW-Authenticate": "X-API-Key"},
)


class AuthContext(BaseModel):
    """The authenticated caller, injected into routes and the rate limiter."""

    client_id: int
    key_id: int
    tier: str
    is_verified: bool = False


def extract_token(request: Request) -> str | None:
    """Pull the token from X-API-Key, falling back to an Authorization bearer."""
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def get_api_client(request: Request, conn: Any = Depends(get_conn)) -> AuthContext:
    token = extract_token(request)
    if not token:
        raise _UNAUTHORIZED
    row = conn.execute(
        """
        select k.id as key_id, k.expires_at, k.revoked_at,
               c.id as client_id, c.tier, c.is_active, c.is_verified
        from api_keys k
        join api_clients c on c.id = k.client_id
        where k.key_hash = %s
        """,
        (hash_key(token),),
    ).fetchone()
    if row is None or not is_key_valid(row, datetime.now(timezone.utc)):
        raise _UNAUTHORIZED
    return AuthContext(
        client_id=row["client_id"], key_id=row["key_id"],
        tier=row["tier"], is_verified=row["is_verified"],
    )
