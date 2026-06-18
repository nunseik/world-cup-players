"""ESPN adapter — secondary / cross-check source (2002-present).

ESPN's World Cup stats only expose player-level Goals and Assists leaderboards
(top ~50 each) plus games played. There are no minutes, fouls, or jersey numbers
(the Discipline view is team-level). We parse the two scoring leaderboards and
merge by player+team; the pipeline uses these to corroborate/fill FBref goals
and assists.
"""

from __future__ import annotations

import structlog
from bs4 import BeautifulSoup

from ..browser import Browser
from ..models import Player, PlayerTournamentStat, Team, normalize_name
from .base import Source

log = structlog.get_logger(__name__)

ESPN_YEARS = frozenset({2002, 2006, 2010, 2014, 2018, 2022, 2026})
SCORING_URL = "https://www.espn.com/soccer/stats/_/league/fifa.world/season/{year}"

# Header label (last column) -> field on PlayerTournamentStat.
_METRIC_FIELDS = {"G": "goals", "A": "assists"}


def _int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value.isdigit() else None


def _headers(table) -> list[str]:  # noqa: ANN001
    head = table.find("thead")
    cells = (head.find_all(["th", "td"]) if head else table.find("tr").find_all(["th", "td"]))
    return [c.get_text(strip=True) for c in cells]


def parse_leaderboards(html: str, year: int) -> list[PlayerTournamentStat]:
    """Parse ESPN's Goals and Assists leaderboard tables into merged stats.

    Pure function so it can be unit-tested against saved fixtures.
    """
    soup = BeautifulSoup(html, "html.parser")
    by_key: dict[tuple[str, str], PlayerTournamentStat] = {}

    for table in soup.find_all("table"):
        headers = _headers(table)
        if "Name" not in headers or headers[-1] not in _METRIC_FIELDS:
            continue  # not a player leaderboard (e.g. team discipline table)
        idx = {h: i for i, h in enumerate(headers)}
        metric_field = _METRIC_FIELDS[headers[-1]]

        body = table.find("tbody") or table
        for tr in body.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) != len(headers):
                continue
            name = cells[idx["Name"]]
            team = cells[idx["Team"]]
            if not name:
                continue
            key = (normalize_name(name), normalize_name(team))
            stat = by_key.get(key)
            if stat is None:
                stat = PlayerTournamentStat(
                    year=year,
                    player=Player(full_name=name),
                    team=Team(name=team) if team else None,
                    appearances=_int(cells[idx["P"]]) if "P" in idx else None,
                    source="espn",
                )
            updates = {metric_field: _int(cells[idx[headers[-1]]])}
            by_key[key] = stat.model_copy(update=updates)

    return list(by_key.values())


class EspnSource(Source):
    name = "espn"
    supported_years = ESPN_YEARS

    async def fetch_stats(self, browser: Browser, year: int) -> list[PlayerTournamentStat]:
        html = await browser.get_html(SCORING_URL.format(year=year), wait_for="table")
        stats = parse_leaderboards(html, year)
        log.info("espn.fetched", year=year, players=len(stats))
        return stats
