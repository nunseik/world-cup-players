"""Player endpoints: list/search, fetch, career aggregate (auth + rate-limited)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import queries
from ..db import get_conn
from ..pagination import PageParams, page_params
from ..rate_limit import rate_limit
from ..schemas import CareerAggregateOut, Page, PlayerOut

router = APIRouter(prefix="/v1/players", tags=["players"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=Page[PlayerOut])
def list_players(
    q: str | None = Query(None, description="Name search (accent/case-insensitive)"),
    position: str | None = None,
    team: str | None = Query(None, description="Team name (aliases canonicalized)"),
    page: PageParams = Depends(page_params),
    conn: Any = Depends(get_conn),
) -> Page[PlayerOut]:
    return queries.list_players(
        conn, q=q, position=position, team=team, limit=page.limit, offset=page.offset
    )


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, conn: Any = Depends(get_conn)) -> PlayerOut:
    p = queries.get_player(conn, player_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"No player with id {player_id}.")
    return p


@router.get("/{player_id}/career", response_model=CareerAggregateOut)
def player_career(player_id: int, conn: Any = Depends(get_conn)) -> CareerAggregateOut:
    c = queries.career_aggregates(conn, player_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"No player with id {player_id}.")
    return c
