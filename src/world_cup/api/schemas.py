"""Wire-format response models for the API.

Deliberately separate from the scraper-shaped domain models in world_cup.models
(which nest player/team, expose computed normalized_name, a source field, and
merge_fill). These are flat, DB-row-shaped contracts so the public API stays
stable even as scraper internals change.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Offset-paginated envelope. `total` is the unfiltered-by-page row count."""

    items: list[T]
    total: int
    limit: int
    offset: int


class TournamentOut(BaseModel):
    year: int
    host_country: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    num_teams: int | None = None


class TeamOut(BaseModel):
    id: int
    name: str
    fifa_code: str | None = None
    confederation: str | None = None


class PlayerOut(BaseModel):
    id: int
    full_name: str
    position: str | None = None
    birth_date: date | None = None


class PlayerStatOut(BaseModel):
    player_id: int
    player_name: str
    team_name: str | None = None
    year: int
    jersey_number: int | None = None
    goals: int | None = None
    assists: int | None = None
    minutes_played: int | None = None
    fouls_committed: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    appearances: int | None = None


class LeaderboardEntryOut(BaseModel):
    rank: int
    player_id: int
    player_name: str
    team_name: str | None = None
    value: int  # goals or assists, depending on the leaderboard


class CareerAggregateOut(BaseModel):
    player_id: int
    player_name: str
    tournaments_played: int
    total_goals: int
    total_assists: int
    total_minutes: int
    total_yellow_cards: int
    total_red_cards: int


class SignupOut(BaseModel):
    """Returned once at signup. The token is never retrievable again."""

    api_key: str
    tier: str
    expires_at: datetime
    message: str = "Store this API key now — it will not be shown again."
