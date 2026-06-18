"""Postgres/Supabase access layer: idempotent upserts keyed on natural keys.

Re-running any scrape is safe — every write is an upsert on a unique constraint,
so loading the same tournament twice updates rows in place instead of duplicating.
"""

from __future__ import annotations

from types import TracebackType

import psycopg

from .config import settings
from .models import Player, PlayerTournamentStat, Team, Tournament, normalize_name


class Database:
    """Thin wrapper over a single psycopg connection with upsert helpers.

    Use as a context manager so the connection is committed and closed cleanly.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or settings.require_db_url()
        self._conn: psycopg.Connection | None = None

    def __enter__(self) -> "Database":
        self._conn = psycopg.connect(self._dsn, autocommit=False)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._conn is not None
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        self._conn = None

    @property
    def conn(self) -> psycopg.Connection:
        if self._conn is None:
            raise RuntimeError("Database must be used as a context manager.")
        return self._conn

    # --- upserts -----------------------------------------------------------

    def upsert_tournament(self, t: Tournament) -> int:
        row = self.conn.execute(
            """
            insert into tournaments (year, host_country, start_date, end_date, num_teams, source_url)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (year) do update set
                host_country = coalesce(excluded.host_country, tournaments.host_country),
                start_date   = coalesce(excluded.start_date, tournaments.start_date),
                end_date     = coalesce(excluded.end_date, tournaments.end_date),
                num_teams    = coalesce(excluded.num_teams, tournaments.num_teams),
                source_url   = coalesce(excluded.source_url, tournaments.source_url)
            returning id
            """,
            (t.year, t.host_country, t.start_date, t.end_date, t.num_teams, t.source_url),
        ).fetchone()
        assert row is not None
        return row[0]

    def tournament_id(self, year: int) -> int | None:
        row = self.conn.execute(
            "select id from tournaments where year = %s", (year,)
        ).fetchone()
        return row[0] if row else None

    def upsert_team(self, team: Team) -> int:
        row = self.conn.execute(
            """
            insert into teams (name, normalized_name, fifa_code, confederation)
            values (%s, %s, %s, %s)
            on conflict (normalized_name) do update set
                name          = excluded.name,
                fifa_code     = coalesce(excluded.fifa_code, teams.fifa_code),
                confederation = coalesce(excluded.confederation, teams.confederation)
            returning id
            """,
            (team.name, team.normalized_name, team.fifa_code, team.confederation),
        ).fetchone()
        assert row is not None
        return row[0]

    def upsert_player(self, player: Player) -> int:
        # Dedup on (normalized_name, birth_date). NULL birth_dates are distinct
        # in Postgres, so a known birth_date can later split a name-only row; we
        # accept that as best-effort identity (documented in the schema).
        row = self.conn.execute(
            """
            insert into players (full_name, normalized_name, birth_date, position)
            values (%s, %s, %s, %s)
            on conflict (normalized_name, birth_date) do update set
                full_name = excluded.full_name,
                position  = coalesce(excluded.position, players.position)
            returning id
            """,
            (player.full_name, normalize_name(player.full_name), player.birth_date, player.position),
        ).fetchone()
        assert row is not None
        return row[0]

    def upsert_stat(self, stat: PlayerTournamentStat) -> None:
        tournament_id = self.tournament_id(stat.year)
        if tournament_id is None:
            raise RuntimeError(
                f"Tournament {stat.year} not seeded. Run seed_tournaments first."
            )
        player_id = self.upsert_player(stat.player)
        team_id = self.upsert_team(stat.team) if stat.team else None
        self.conn.execute(
            """
            insert into player_tournament_stats (
                player_id, team_id, tournament_id, jersey_number, goals, assists,
                minutes_played, fouls_committed, yellow_cards, red_cards, appearances, source
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (player_id, tournament_id) do update set
                team_id         = coalesce(excluded.team_id, player_tournament_stats.team_id),
                jersey_number   = coalesce(excluded.jersey_number, player_tournament_stats.jersey_number),
                goals           = coalesce(excluded.goals, player_tournament_stats.goals),
                assists         = coalesce(excluded.assists, player_tournament_stats.assists),
                minutes_played  = coalesce(excluded.minutes_played, player_tournament_stats.minutes_played),
                fouls_committed = coalesce(excluded.fouls_committed, player_tournament_stats.fouls_committed),
                yellow_cards    = coalesce(excluded.yellow_cards, player_tournament_stats.yellow_cards),
                red_cards       = coalesce(excluded.red_cards, player_tournament_stats.red_cards),
                appearances     = coalesce(excluded.appearances, player_tournament_stats.appearances),
                source          = excluded.source,
                scraped_at      = now()
            """,
            (
                player_id, team_id, tournament_id, stat.jersey_number, stat.goals,
                stat.assists, stat.minutes_played, stat.fouls_committed,
                stat.yellow_cards, stat.red_cards, stat.appearances, stat.source,
            ),
        )

    # --- scrape_runs -------------------------------------------------------

    def start_run(self, year: int | None, source: str) -> int:
        row = self.conn.execute(
            "insert into scrape_runs (year, source, status) values (%s, %s, 'running') returning id",
            (year, source),
        ).fetchone()
        assert row is not None
        self.conn.commit()  # persist the run marker immediately
        return row[0]

    def finish_run(self, run_id: int, *, status: str, records: int, error: str | None = None) -> None:
        self.conn.execute(
            """
            update scrape_runs
            set status = %s, records_upserted = %s, error = %s, finished_at = now()
            where id = %s
            """,
            (status, records, error, run_id),
        )
