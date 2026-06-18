"""FastAPI application: lifespan-managed pools, health check, mounted routers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import psycopg
from fastapi import Depends, FastAPI

from .db import close_pools, get_conn, open_pools
from .routers import players, signup, stats, teams, tournaments


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pools()
    try:
        yield
    finally:
        close_pools()


def create_app() -> FastAPI:
    app = FastAPI(
        title="World Cup Players API",
        version="0.1.0",
        description="Read-only API for FIFA World Cup player stats (1970–present).",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["meta"])
    def health(conn: Any = Depends(get_conn)) -> dict[str, str]:
        try:
            conn.execute("select 1")
            db = "ok"
        except psycopg.Error:
            db = "down"
        return {"status": "ok", "db": db}

    for module in (signup, tournaments, players, stats, teams):
        app.include_router(module.router)
    return app


app = create_app()
