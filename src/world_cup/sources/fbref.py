"""FBref (Sports Reference) adapter — primary source.

FBref publishes full World Cup rosters with minutes, goals, assists, cards
(the "Standard Stats" table) and fouls committed (the "Miscellaneous Stats"
table). We fetch both and merge by player+squad. Jersey numbers are not in
these aggregate tables (they live on squad/lineup pages) — left null for now.

Tables are keyed by FBref's stable `data-stat` attributes, which makes the
parser robust to layout/CSS changes and testable against saved HTML fixtures.

NOTE: FBref is behind Cloudflare; see browser.py. Live validation must run from
a non-datacenter network.
"""

from __future__ import annotations

import re

import structlog
from bs4 import BeautifulSoup

from ..browser import Browser
from ..models import Player, PlayerTournamentStat, Team, normalize_name
from .base import Source

log = structlog.get_logger(__name__)

COMP_ID = 1  # FIFA World Cup competition id on FBref
STANDARD_URL = "https://fbref.com/en/comps/{comp}/{year}/stats/{year}-World-Cup-Stats"
MISC_URL = "https://fbref.com/en/comps/{comp}/{year}/misc/{year}-World-Cup-Stats"


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.replace(",", "").strip()
    if not cleaned or not cleaned.lstrip("-").isdigit():
        return None
    return int(cleaned)


def _str(value: str | None) -> str | None:
    return value.strip() or None if value else None


# FBref squad cells glue a lowercase country code onto the country name, because
# the flag/code and the squad link are adjacent elements that collapse together
# when we read cell text ("frFrance", "arArgentina", "engEngland", "wlsWales").
# The code is the leading run of lowercase letters before the first uppercase.
# Strip it so team names match ESPN's plain form ("France") when merging sources.
_SQUAD_CODE_RE = re.compile(r"^[a-z]+\s*(?=[A-Z])")


def _team(value: str | None) -> str | None:
    name = _str(value)
    return _SQUAD_CODE_RE.sub("", name, count=1) if name else None


def parse_table(html: str, id_prefix: str) -> list[dict[str, str]]:
    """Return one dict (data-stat -> cell text) per real data row.

    Robust to: FBref wrapping secondary tables in HTML comments, repeated header
    rows inside the body, and spacer rows. Only rows with a non-empty `player`
    cell are returned.
    """
    # FBref hides some tables inside HTML comments; un-hide before parsing.
    soup = BeautifulSoup(html.replace("<!--", "").replace("-->", ""), "html.parser")

    table = next(
        (t for t in soup.find_all("table") if (t.get("id") or "").startswith(id_prefix)),
        None,
    )
    if table is None:
        return []

    body = table.find("tbody") or table
    rows: list[dict[str, str]] = []
    for tr in body.find_all("tr"):
        classes = tr.get("class") or []
        if {"thead", "over_header", "spacer", "partial_table"} & set(classes):
            continue
        cells = {
            cell["data-stat"]: cell.get_text(strip=True)
            for cell in tr.find_all(["th", "td"])
            if cell.get("data-stat")
        }
        if cells.get("player"):
            rows.append(cells)
    return rows


def _row_to_stat(year: int, row: dict[str, str]) -> PlayerTournamentStat:
    team_name = _team(row.get("team"))
    return PlayerTournamentStat(
        year=year,
        player=Player(full_name=row["player"], position=_str(row.get("position"))),
        team=Team(name=team_name) if team_name else None,
        appearances=_int(row.get("games")),
        minutes_played=_int(row.get("minutes")),
        goals=_int(row.get("goals")),
        assists=_int(row.get("assists")),
        yellow_cards=_int(row.get("cards_yellow")),
        red_cards=_int(row.get("cards_red")),
        source="fbref",
    )


def _key(name: str, team: str | None) -> tuple[str, str]:
    return (normalize_name(name), normalize_name(team) if team else "")


def build_stats(standard_html: str, misc_html: str | None, year: int) -> list[PlayerTournamentStat]:
    """Parse the standard table, then enrich with fouls from the misc table.

    Pure function (no I/O) so it can be unit-tested against fixtures.
    """
    by_key: dict[tuple[str, str], PlayerTournamentStat] = {}
    for row in parse_table(standard_html, "stats_standard"):
        stat = _row_to_stat(year, row)
        by_key[_key(stat.player.full_name, stat.team.name if stat.team else None)] = stat

    if misc_html:
        for row in parse_table(misc_html, "stats_misc"):
            fouls = _int(row.get("fouls"))
            key = _key(row["player"], _team(row.get("team")))
            if fouls is not None and key in by_key:
                by_key[key] = by_key[key].model_copy(update={"fouls_committed": fouls})

    return list(by_key.values())


class FbrefSource(Source):
    name = "fbref"
    supported_years = frozenset()  # FBref covers all World Cups (1930+)

    async def fetch_stats(self, browser: Browser, year: int) -> list[PlayerTournamentStat]:
        standard_html = await browser.get_html(
            STANDARD_URL.format(comp=COMP_ID, year=year), wait_for="table"
        )
        # Fouls live on a separate page; best-effort (older years may lack it).
        misc_html: str | None = None
        try:
            misc_html = await browser.get_html(
                MISC_URL.format(comp=COMP_ID, year=year), wait_for="table"
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("fbref.misc_unavailable", year=year, error=str(exc))

        stats = build_stats(standard_html, misc_html, year)
        log.info("fbref.fetched", year=year, players=len(stats))
        return stats
