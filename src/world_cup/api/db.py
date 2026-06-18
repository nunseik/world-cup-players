"""Connection pools and FastAPI DB dependencies for the API server.

Unlike the scraper's per-use Database (a fresh connect() each time — fine for a
batch job), a long-running server amortizes the TCP+TLS+auth handshake with a
process-level pool. Two pools:

  * read pool  — read_only connections for the public data endpoints, so the
                 API physically cannot write through that path.
  * write pool — a small writable pool used only by auth/rate-limit bookkeeping
                 (last_used_at, rate counters), which are genuine writes.

Pools are opened/closed by app.py's lifespan. The get_* functions are FastAPI
dependencies; tests override them with fakes so the suite needs no live DB.
"""

from __future__ import annotations

from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..config import settings

_read_pool: ConnectionPool | None = None
_write_pool: ConnectionPool | None = None


def _configure_read(conn: psycopg.Connection) -> None:
    conn.row_factory = dict_row
    conn.autocommit = True
    conn.read_only = True


def _configure_write(conn: psycopg.Connection) -> None:
    conn.row_factory = dict_row
    conn.autocommit = True  # each bookkeeping write is a single self-contained statement


def open_pools() -> None:
    """Open both pools. Called from the app lifespan on startup."""
    global _read_pool, _write_pool
    if _read_pool is not None:
        return
    read_dsn = settings.read_only_db_url()
    write_dsn = settings.require_db_url()
    _read_pool = ConnectionPool(
        read_dsn, min_size=settings.api_pool_min, max_size=settings.api_pool_max,
        configure=_configure_read, open=True, kwargs={"autocommit": True},
    )
    # The write path is light (a couple of statements per request) — keep it tiny.
    _write_pool = ConnectionPool(
        write_dsn, min_size=1, max_size=max(2, settings.api_pool_min),
        configure=_configure_write, open=True, kwargs={"autocommit": True},
    )


def close_pools() -> None:
    """Close both pools. Called from the app lifespan on shutdown."""
    global _read_pool, _write_pool
    if _read_pool is not None:
        _read_pool.close()
        _read_pool = None
    if _write_pool is not None:
        _write_pool.close()
        _write_pool = None


def get_conn() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: a read-only pooled connection for data endpoints."""
    if _read_pool is None:
        raise RuntimeError("Read pool is not open. Did the app lifespan run?")
    with _read_pool.connection() as conn:
        yield conn


def get_writable() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: a writable pooled connection for auth/rate-limit writes."""
    if _write_pool is None:
        raise RuntimeError("Write pool is not open. Did the app lifespan run?")
    with _write_pool.connection() as conn:
        yield conn
