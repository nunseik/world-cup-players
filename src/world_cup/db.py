"""Postgres/Supabase access layer: idempotent upserts keyed on natural keys.

Re-running any scrape is safe — every write is an upsert on a unique constraint,
so loading the same tournament twice updates rows in place instead of duplicating.
"""

from __future__ import annotations

from types import TracebackType

import psycopg

from .config import settings
from .models import Player, PlayerTournamentStat, Team, Tournament


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

    def upsert_stats_bulk(self, stats: list[PlayerTournamentStat]) -> int:
        """Upsert one year's stats, batching round-trips with pipelined executemany.

        Replaces per-player synchronous round-trips (tournament lookup + player +
        team + stat, ~4 each) with `executemany(returning=True)`, which psycopg
        pipelines into a few network flushes — a ~700-row year drops from minutes
        to seconds. Each row is still its own statement, so on-conflict semantics
        (and the null-birth_date identity quirk) exactly match the former path.

        Mapping is by **position**, not by natural key: executemany returns ids in
        input order, so two distinct players who share a name with null birth_date
        (e.g. the two Carlos Sánchez in 2018) each keep their own row. Returns the
        number of stat rows written.
        """
        if not stats:
            return 0
        years = {s.year for s in stats}
        if len(years) != 1:
            raise ValueError(f"upsert_stats_bulk expects a single year, got {sorted(years)}")
        tournament_id = self.tournament_id(years.pop())
        if tournament_id is None:
            raise RuntimeError(
                f"Tournament {stats[0].year} not seeded. Run seed_tournaments first."
            )

        # Teams dedup by normalized_name (a real conflict key); players do not —
        # one row per stat, positionally mapped back to its stat below.
        teams = list({s.team.normalized_name: s.team for s in stats if s.team}.values())
        team_ids = self._bulk_upsert_teams(teams)
        player_ids = self._bulk_upsert_players([s.player for s in stats])

        params = [
            (
                player_ids[i],
                team_ids.get(s.team.normalized_name) if s.team else None,
                tournament_id, s.jersey_number, s.goals, s.assists, s.minutes_played,
                s.fouls_committed, s.yellow_cards, s.red_cards, s.appearances, s.source,
            )
            for i, s in enumerate(stats)
        ]
        self.conn.cursor().executemany(
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
            params,
        )
        return len(stats)

    def _bulk_upsert_teams(self, teams: list[Team]) -> dict[str, int]:
        """Upsert teams (unique by normalized_name); return {normalized_name: id}."""
        if not teams:
            return {}
        ids = self._executemany_returning(
            """
            insert into teams (name, normalized_name, fifa_code, confederation)
            values (%s, %s, %s, %s)
            on conflict (normalized_name) do update set
                name          = excluded.name,
                fifa_code     = coalesce(excluded.fifa_code, teams.fifa_code),
                confederation = coalesce(excluded.confederation, teams.confederation)
            returning id
            """,
            [(t.name, t.normalized_name, t.fifa_code, t.confederation) for t in teams],
        )
        return {t.normalized_name: i for t, i in zip(teams, ids)}

    def _bulk_upsert_players(self, players: list[Player]) -> list[int]:
        """Upsert one row per player; return ids aligned to the input order.

        NULL birth_dates are distinct in Postgres, so name-only rows never collapse
        and re-running a year creates fresh rows — the documented best-effort
        identity (see this module's header / CLAUDE.md).
        """
        if not players:
            return []
        return self._executemany_returning(
            """
            insert into players (full_name, normalized_name, birth_date, position)
            values (%s, %s, %s, %s)
            on conflict (normalized_name, birth_date) do update set
                full_name = excluded.full_name,
                position  = coalesce(excluded.position, players.position)
            returning id
            """,
            [(p.full_name, p.normalized_name, p.birth_date, p.position) for p in players],
        )

    def _executemany_returning(self, query: str, params_seq: list[tuple]) -> list[int]:
        """Run `query` once per param tuple (pipelined) and collect the single
        returned id from each, in input order."""
        cur = self.conn.cursor()
        cur.executemany(query, params_seq, returning=True)
        ids: list[int] = []
        while True:
            ids.extend(row[0] for row in cur.fetchall())
            if not cur.nextset():
                break
        return ids

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
