"""Tournament + leaderboard endpoints (auth + rate-limited)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import queries
from ..db import get_conn
from ..rate_limit import rate_limit
from ..schemas import LeaderboardEntryOut, Page, TournamentOut

router = APIRouter(prefix="/v1/tournaments", tags=["tournaments"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=Page[TournamentOut])
def list_tournaments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: Any = Depends(get_conn),
) -> Page[TournamentOut]:
    return queries.list_tournaments(conn, limit=limit, offset=offset)


@router.get("/{year}", response_model=TournamentOut)
def get_tournament(year: int, conn: Any = Depends(get_conn)) -> TournamentOut:
    t = queries.get_tournament(conn, year)
    if t is None:
        raise HTTPException(status_code=404, detail=f"No tournament for {year}.")
    return t


@router.get("/{year}/leaderboards/scorers", response_model=list[LeaderboardEntryOut])
def top_scorers(
    year: int, limit: int = Query(10, ge=1, le=100), conn: Any = Depends(get_conn)
) -> list[LeaderboardEntryOut]:
    return queries.leaderboard(conn, year, "scorers", limit)


@router.get("/{year}/leaderboards/assists", response_model=list[LeaderboardEntryOut])
def top_assists(
    year: int, limit: int = Query(10, ge=1, le=100), conn: Any = Depends(get_conn)
) -> list[LeaderboardEntryOut]:
    return queries.leaderboard(conn, year, "assists", limit)
