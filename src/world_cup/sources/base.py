"""Source interface. Each adapter knows how to fetch player stats for a year."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..browser import Browser
from ..models import PlayerTournamentStat


class Source(ABC):
    """A stats provider (ESPN, FIFA, ...).

    Adapters receive a live `Browser` so they can navigate/scrape, and return
    normalized `PlayerTournamentStat` objects. They must not touch the database.
    """

    #: short identifier stored on each stat row (e.g. "espn").
    name: str

    #: years this source can serve (used by the pipeline to skip impossible work).
    supported_years: frozenset[int] = frozenset()

    @abstractmethod
    async def fetch_stats(self, browser: Browser, year: int) -> list[PlayerTournamentStat]:
        """Return all player-tournament stats for the given World Cup year."""
        raise NotImplementedError

    def supports(self, year: int) -> bool:
        return not self.supported_years or year in self.supported_years
