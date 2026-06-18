"""Stats endpoint: filterable, sortable player-tournament rows (auth + rate-limited)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from .. import queries
from ..db import get_conn
from ..rate_limit import rate_limit
from ..schemas import Page, PlayerStatOut

router = APIRouter(prefix="/v1/stats", tags=["stats"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=Page[PlayerStatOut])
def list_stats(
    year: int | None = None,
    team: str | None = Query(None, description="Team name (aliases canonicalized)"),
    player_id: int | None = None,
    position: str | None = None,
    min_goals: int | None = Query(None, ge=0),
    sort: str | None = Query(
        None,
        description="goals|assists|minutes|appearances|yellow_cards|red_cards; prefix '-' for desc",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: Any = Depends(get_conn),
) -> Page[PlayerStatOut]:
    return queries.list_stats(
        conn, year=year, team=team, player_id=player_id, position=position,
        min_goals=min_goals, sort=sort, limit=limit, offset=offset,
    )
