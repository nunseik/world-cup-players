"""Atomic refresh of one tournament year using ESPN as the sole source.

Scrapes first, then — only on success — replaces the old rows in a single
transaction so a failed fetch never leaves the DB half-empty.

Usage:
    uv run python scripts/refresh_year.py 2026
"""

import asyncio
import sys

import structlog

log = structlog.get_logger(__name__)


async def refresh(year: int) -> None:
    from world_cup.db import Database
    from world_cup.pipeline import scrape_year
    from world_cup.sources.espn import EspnSource

    log.info("refresh.start", year=year)
    stats = await scrape_year(year, primary=EspnSource(), use_fallback=False)
    if not stats:
        log.error("refresh.empty", year=year)
        sys.exit(1)

    with Database() as db:
        run_id = db.start_run(year, source="espn-refresh")
        try:
            tournament_id = db.tournament_id(year)
            if tournament_id is None:
                raise RuntimeError(f"Tournament {year} not in DB — seed it first.")

            # Delete this year's stats, then orphaned players, then reload — all
            # in one transaction so a failed reload rolls back to the old data.
            db.conn.execute(
                "DELETE FROM player_tournament_stats WHERE tournament_id = %s",
                (tournament_id,),
            )
            db.conn.execute(
                """
                DELETE FROM players
                WHERE id NOT IN (
                    SELECT DISTINCT player_id FROM player_tournament_stats
                )
                """
            )

            written = db.upsert_stats_bulk(stats)
            db.finish_run(run_id, status="success", records=written)
            log.info("refresh.done", year=year, rows=written)
        except Exception as exc:
            db.finish_run(run_id, status="error", records=0, error=str(exc))
            raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/refresh_year.py <year>")
        sys.exit(1)
    asyncio.run(refresh(int(sys.argv[1])))
