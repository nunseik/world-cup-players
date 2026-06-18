"""API key generation, hashing, validation, and issuance.

Pure helpers (generate/hash/validate) carry no DB dependency so they unit-test
without a database; issue_key/list_keys/revoke_key take a connection and are
shared by both the public signup endpoint and the admin CLI (world-cup api-key).

Storage rule: we persist only the SHA-256 hash of a token, never the plaintext.
Tokens are high-entropy random strings, so SHA-256 (not a slow password KDF) is
the right choice — there is no low-entropy secret to protect against brute force.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from ..config import settings

# Recognizable, greppable prefix on every token (helps users/logs spot a key).
KEY_PREFIX = "wc_"
# How many leading chars to store in clear for display/identification.
PREFIX_DISPLAY_LEN = 11  # "wc_" + 8 token chars


@dataclass(frozen=True)
class GeneratedKey:
    token: str        # plaintext, returned to the user exactly once
    key_hash: str     # sha256 hex, what we store
    key_prefix: str   # leading chars, stored in clear for display


def hash_key(token: str) -> str:
    """SHA-256 hex digest of a token. Deterministic; used for storage + lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_key() -> GeneratedKey:
    """Mint a fresh token plus its hash and display prefix."""
    token = KEY_PREFIX + secrets.token_urlsafe(32)
    return GeneratedKey(
        token=token,
        key_hash=hash_key(token),
        key_prefix=token[:PREFIX_DISPLAY_LEN],
    )


def is_key_valid(row: Mapping[str, Any], now: datetime) -> bool:
    """Whether a joined api_keys+api_clients row authorizes a request at `now`.

    Pure predicate over the row fields so it tests without a DB. Expects keys:
    expires_at, revoked_at, is_active.
    """
    if not row.get("is_active", False):
        return False
    if row.get("revoked_at") is not None:
        return False
    expires_at = row.get("expires_at")
    if expires_at is None or expires_at <= now:
        return False
    return True


# --- DB-backed operations (shared by signup endpoint + admin CLI) -----------


def issue_key(
    conn: Any,
    email: str,
    *,
    tier: str = "free",
    days: int | None = None,
    name: str | None = None,
    verified: bool = False,
) -> tuple[str, datetime]:
    """Find-or-create the client for `email`, set its tier, and mint a key.

    Returns (plaintext_token, expires_at). The token is not stored anywhere in
    plaintext — surface it to the caller immediately and once. Writes; the caller
    owns the transaction/commit. `verified` is True for admin issuance and False
    for self-serve signup; verification is monotonic (re-signup never un-verifies).
    """
    ttl_days = days if days is not None else settings.api_key_ttl_days
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    client = conn.execute(
        """
        insert into api_clients (email, name, tier, is_verified)
        values (%s, %s, %s, %s)
        on conflict (email) do update set
            tier = excluded.tier,
            name = coalesce(excluded.name, api_clients.name),
            is_verified = api_clients.is_verified or excluded.is_verified
        returning id
        """,
        (email, name, tier, verified),
    ).fetchone()
    client_id = client[0] if not isinstance(client, Mapping) else client["id"]

    key = generate_key()
    conn.execute(
        """
        insert into api_keys (client_id, key_hash, key_prefix, expires_at)
        values (%s, %s, %s, %s)
        """,
        (client_id, key.key_hash, key.key_prefix, expires_at),
    )
    return key.token, expires_at


def set_tier(conn: Any, email: str, tier: str) -> bool:
    """Change a client's tier. Returns False if no client has that email."""
    row = conn.execute(
        "update api_clients set tier = %s where email = %s returning id",
        (tier, email),
    ).fetchone()
    return row is not None


def verify_client(conn: Any, email: str) -> bool:
    """Mark a client verified (lifts the unverified limits). False if not found."""
    row = conn.execute(
        "update api_clients set is_verified = true where email = %s returning id",
        (email,),
    ).fetchone()
    return row is not None


def revoke_key(conn: Any, *, prefix: str | None = None, key_id: int | None = None) -> int:
    """Soft-revoke matching active keys (by prefix or id). Returns rows revoked."""
    if key_id is not None:
        cur = conn.execute(
            "update api_keys set revoked_at = now() where id = %s and revoked_at is null",
            (key_id,),
        )
    elif prefix is not None:
        cur = conn.execute(
            "update api_keys set revoked_at = now() where key_prefix = %s and revoked_at is null",
            (prefix,),
        )
    else:
        raise ValueError("revoke_key needs either prefix or key_id")
    return cur.rowcount


def list_keys(conn: Any, *, email: str | None = None) -> list[dict[str, Any]]:
    """List keys with their owning client, newest first; optionally filter by email."""
    sql = """
        select k.id, k.key_prefix, c.email, c.tier, c.is_active,
               k.created_at, k.expires_at, k.revoked_at, k.last_used_at
        from api_keys k
        join api_clients c on c.id = k.client_id
    """
    params: tuple = ()
    if email is not None:
        sql += " where c.email = %s"
        params = (email,)
    sql += " order by k.created_at desc"
    rows = conn.execute(sql, params).fetchall()
    cols = ("id", "key_prefix", "email", "tier", "is_active",
            "created_at", "expires_at", "revoked_at", "last_used_at")
    return [dict(zip(cols, r)) for r in rows]
