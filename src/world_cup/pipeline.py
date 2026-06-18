"""Orchestration: scrape a tournament from sources, merge, and load to DB.

Flow per year:
  1. primary source (ESPN) -> list[PlayerTournamentStat]
  2. fallback source (FIFA) fills null fields, merged by (player, team)
  3. upsert players/teams/stats; record a scrape_runs row

`--dry-run` skips steps 3 and prints the normalized rows instead.
"""

from __future__ import annotations

import structlog

from .browser import Browser
from .models import PlayerTournamentStat, canonical_team_name, normalize_name
from .sources.base import Source
from .sources.espn import EspnSource
from .sources.fbref import FbrefSource

log = structlog.get_logger(__name__)


def _key(stat: PlayerTournamentStat) -> tuple[str, str]:
    team = canonical_team_name(stat.team.name) if stat.team else ""
    return (normalize_name(stat.player.full_name), team)


def merge_sources(
    primary: list[PlayerTournamentStat],
    fallback: list[PlayerTournamentStat],
) -> list[PlayerTournamentStat]:
    """Fill null fields on primary rows from matching fallback rows.

    Matching is by (normalized player name, normalized team). Fallback rows with
    no primary match are appended so we don't silently drop data.
    """
    by_key = {_key(s): s for s in primary}
    for fb in fallback:
        existing = by_key.get(_key(fb))
        by_key[_key(fb)] = existing.merge_fill(fb) if existing else fb
    return list(by_key.values())


async def scrape_year(
    year: int,
    *,
    primary: Source | None = None,
    fallback: Source | None = None,
    use_fallback: bool = True,
) -> list[PlayerTournamentStat]:
    """Scrape and merge a single year's stats. No DB writes.

    Primary = FBref (full rosters: minutes, goals, assists, cards, fouls).
    Fallback = ESPN (goals/assists leaderboards) to corroborate/fill gaps.
    """
    primary = primary or FbrefSource()
    fallback = fallback or EspnSource()

    async with Browser() as browser:
        primary_stats: list[PlayerTournamentStat] = []
        if primary.supports(year):
            primary_stats = await primary.fetch_stats(browser, year)
        else:
            log.info("source.skip", source=primary.name, year=year)

        fallback_stats: list[PlayerTournamentStat] = []
        if use_fallback and fallback.supports(year):
            fallback_stats = await fallback.fetch_stats(browser, year)

    merged = merge_sources(primary_stats, fallback_stats)
    log.info("scrape_year.done", year=year, primary=len(primary_stats),
             fallback=len(fallback_stats), merged=len(merged))
    return merged


async def run_year(
    year: int,
    *,
    dry_run: bool,
    primary: Source | None = None,
    fallback: Source | None = None,
    use_fallback: bool = True,
) -> list[PlayerTournamentStat]:
    """Scrape one year and (unless dry_run) load it, recording a scrape_runs row."""
    primary = primary or FbrefSource()
    fallback = fallback or EspnSource()
    run_source = primary.name + ("+" + fallback.name if use_fallback else "")

    if dry_run:
        return await scrape_year(year, primary=primary, fallback=fallback, use_fallback=use_fallback)

    # Import here so --dry-run never requires a DB connection.
    from .db import Database

    with Database() as db:
        run_id = db.start_run(year, source=run_source)
        try:
            stats = await scrape_year(
                year, primary=primary, fallback=fallback, use_fallback=use_fallback
            )
            written = db.upsert_stats_bulk(stats)
            db.finish_run(run_id, status="success", records=written)
            return stats
        except Exception as exc:  # noqa: BLE001 - record then re-raise
            db.finish_run(run_id, status="error", records=0, error=str(exc))
            raise
