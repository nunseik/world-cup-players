"""Pure tests for key generation, hashing, and validation (no DB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from world_cup.api.keys import KEY_PREFIX, generate_key, hash_key, is_key_valid

NOW = datetime(2026, 6, 18, tzinfo=timezone.utc)


def test_generate_key_is_unique_and_prefixed():
    a, b = generate_key(), generate_key()
    assert a.token != b.token
    assert a.token.startswith(KEY_PREFIX)
    assert a.key_prefix == a.token[: len(a.key_prefix)]


def test_hash_is_deterministic_and_not_plaintext():
    g = generate_key()
    assert g.key_hash == hash_key(g.token)
    assert g.token not in g.key_hash
    assert len(g.key_hash) == 64  # sha256 hex


def _row(**over):
    base = {"is_active": True, "revoked_at": None, "expires_at": NOW + timedelta(days=1)}
    base.update(over)
    return base


def test_valid_key_passes():
    assert is_key_valid(_row(), NOW) is True


def test_expired_key_rejected():
    assert is_key_valid(_row(expires_at=NOW - timedelta(seconds=1)), NOW) is False


def test_revoked_key_rejected():
    assert is_key_valid(_row(revoked_at=NOW), NOW) is False


def test_inactive_client_rejected():
    assert is_key_valid(_row(is_active=False), NOW) is False
