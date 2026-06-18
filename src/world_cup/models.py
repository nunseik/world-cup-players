"""Domain models shared across sources, pipeline, and DB layer."""

from __future__ import annotations

import unicodedata
from datetime import date

from pydantic import BaseModel, Field


def normalize_name(name: str) -> str:
    """Lowercase, strip accents and collapse whitespace for dedup keys.

    e.g. "Kylian Mbappé" -> "kylian mbappe".
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


# FBref and ESPN disagree on some national-team names. We canonicalize to FBref's
# form (the primary source) so cross-source rows merge and each team is stored
# once. Keys and values are both normalize_name() output (lowercase, accents
# stripped). Verified against 2022 (Iran, South Korea); extend as later
# tournaments surface more mismatches. An alias whose source name never appears
# is simply inert, so extra entries are safe.
_TEAM_ALIASES = {
    "south korea": "korea republic",
    "north korea": "korea dpr",
    "iran": "ir iran",
    "china": "china pr",
    "usa": "united states",
    "ivory coast": "cote d'ivoire",
    "republic of ireland": "rep. of ireland",  # ESPN spells it out; FBref abbreviates
    "bosnia-herzegovina": "bosnia & herz.",     # ESPN hyphenates; FBref abbreviates
}


def canonical_team_name(name: str) -> str:
    """Normalized team name mapped to FBref's canonical form via the alias table.

    Used as the team component of the cross-source merge key and the DB dedup key,
    so e.g. ESPN's "South Korea" and FBref's "Korea Republic" resolve to one team.
    """
    normalized = normalize_name(name)
    return _TEAM_ALIASES.get(normalized, normalized)


class Tournament(BaseModel):
    year: int
    host_country: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    num_teams: int | None = None
    source_url: str | None = None


class Team(BaseModel):
    name: str
    fifa_code: str | None = None
    confederation: str | None = None

    @property
    def normalized_name(self) -> str:
        return canonical_team_name(self.name)


class Player(BaseModel):
    full_name: str
    birth_date: date | None = None
    position: str | None = None

    @property
    def normalized_name(self) -> str:
        return normalize_name(self.full_name)


class PlayerTournamentStat(BaseModel):
    """One player's totals for one World Cup, plus the team they played for.

    All stat fields are optional: older tournaments only have a subset.
    """

    year: int
    player: Player
    team: Team | None = None

    jersey_number: int | None = None
    goals: int | None = None
    assists: int | None = None
    minutes_played: int | None = None
    fouls_committed: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    appearances: int | None = None

    source: str = Field(description="'espn' | 'fifa' | 'wikipedia'")

    def merge_fill(self, other: "PlayerTournamentStat") -> "PlayerTournamentStat":
        """Return a copy with any null stat fields filled from `other`.

        Used by the pipeline so a fallback source (FIFA) can supply fields the
        primary source (ESPN) left null, without overwriting existing values.
        """
        stat_fields = (
            "jersey_number",
            "goals",
            "assists",
            "minutes_played",
            "fouls_committed",
            "yellow_cards",
            "red_cards",
            "appearances",
        )
        updates: dict[str, object] = {}
        for field in stat_fields:
            if getattr(self, field) is None and getattr(other, field) is not None:
                updates[field] = getattr(other, field)
        if self.team is None and other.team is not None:
            updates["team"] = other.team
        return self.model_copy(update=updates)
