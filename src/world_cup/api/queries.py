"""Pure read queries: take a (dict_row) connection, return response models.

No FastAPI, no pool, no globals — so they unit-test against any connection (or a
fake). Raw parameterized SQL, matching the repo's no-ORM convention. Sorting is
whitelisted (never interpolate user input as SQL).
"""

from __future__ import annotations

from typing import Any

from ..models import canonical_team_name, normalize_name
from .schemas import (
    CareerAggregateOut,
    LeaderboardEntryOut,
    Page,
    PlayerOut,
    PlayerStatOut,
    TeamOut,
    TournamentOut,
)

# Columns a client may sort /v1/stats by. Maps the public name to its SQL column.
_STAT_SORT_COLUMNS = {
    "goals": "s.goals",
    "assists": "s.assists",
    "minutes": "s.minutes_played",
    "appearances": "s.appearances",
    "yellow_cards": "s.yellow_cards",
    "red_cards": "s.red_cards",
}


def _scalar(conn: Any, sql: str, params: tuple) -> int:
    row = conn.execute(sql, params).fetchone()
    # dict_row -> single-column dict; pull the only value.
    return int(next(iter(row.values()))) if row else 0


def list_tournaments(conn: Any, *, limit: int, offset: int) -> Page[TournamentOut]:
    total = _scalar(conn, "select count(*) from tournaments", ())
    rows = conn.execute(
        """
        select year, host_country, start_date, end_date, num_teams
        from tournaments order by year desc limit %s offset %s
        """,
        (limit, offset),
    ).fetchall()
    return Page(items=[TournamentOut(**r) for r in rows], total=total, limit=limit, offset=offset)


def get_tournament(conn: Any, year: int) -> TournamentOut | None:
    row = conn.execute(
        """
        select year, host_country, start_date, end_date, num_teams
        from tournaments where year = %s
        """,
        (year,),
    ).fetchone()
    return TournamentOut(**row) if row else None


def list_teams(conn: Any, *, confederation: str | None, limit: int, offset: int) -> Page[TeamOut]:
    where, params = "", []
    if confederation:
        where = "where confederation = %s"
        params.append(confederation)
    total = _scalar(conn, f"select count(*) from teams {where}", tuple(params))
    rows = conn.execute(
        f"""
        select id, name, fifa_code, confederation
        from teams {where} order by name limit %s offset %s
        """,
        (*params, limit, offset),
    ).fetchall()
    return Page(items=[TeamOut(**r) for r in rows], total=total, limit=limit, offset=offset)


def list_players(
    conn: Any, *, q: str | None, position: str | None, team: str | None,
    limit: int, offset: int,
) -> Page[PlayerOut]:
    clauses, params = [], []
    join = ""
    if q:
        clauses.append("p.normalized_name like %s")
        params.append(f"%{normalize_name(q)}%")
    if position:
        clauses.append("p.position = %s")
        params.append(position)
    if team:
        # Players join stats->teams; canonicalize the team name to its stored form.
        join = (
            " join player_tournament_stats s on s.player_id = p.id"
            " join teams t on t.id = s.team_id"
        )
        clauses.append("t.normalized_name = %s")
        params.append(canonical_team_name(team))
    where = ("where " + " and ".join(clauses)) if clauses else ""
    # Collapse by normalized_name: birth_date is uniformly null, so the
    # (normalized_name, birth_date) identity splits every multi-tournament player
    # into one row per edition. Group by name to present one person; the returned
    # id is a representative row (min id) the career endpoint re-expands by name.
    total = _scalar(
        conn,
        f"select count(distinct p.normalized_name) from players p{join} {where}",
        tuple(params),
    )
    rows = conn.execute(
        f"""
        select min(p.id) as id, min(p.full_name) as full_name,
               max(p.position) as position, max(p.birth_date) as birth_date
        from players p{join} {where}
        group by p.normalized_name
        order by min(p.full_name) limit %s offset %s
        """,
        (*params, limit, offset),
    ).fetchall()
    return Page(items=[PlayerOut(**r) for r in rows], total=total, limit=limit, offset=offset)


def get_player(conn: Any, player_id: int) -> PlayerOut | None:
    row = conn.execute(
        "select id, full_name, position, birth_date from players where id = %s",
        (player_id,),
    ).fetchone()
    return PlayerOut(**row) if row else None


def career_aggregates(conn: Any, player_id: int) -> CareerAggregateOut | None:
    # Aggregate across every player row sharing this one's normalized_name, so a
    # player split into one row per edition (null birth_date) yields a true
    # all-tournaments career total. min(id)/min(name) give a stable representative.
    row = conn.execute(
        """
        select min(p.id) as player_id, min(p.full_name) as player_name,
               count(s.id)                      as tournaments_played,
               coalesce(sum(s.goals), 0)        as total_goals,
               coalesce(sum(s.assists), 0)      as total_assists,
               coalesce(sum(s.minutes_played), 0) as total_minutes,
               coalesce(sum(s.yellow_cards), 0) as total_yellow_cards,
               coalesce(sum(s.red_cards), 0)    as total_red_cards
        from players p
        left join player_tournament_stats s on s.player_id = p.id
        where p.normalized_name = (select normalized_name from players where id = %s)
        """,
        (player_id,),
    ).fetchone()
    # The aggregate always returns one row; a missing id yields null player_id.
    return CareerAggregateOut(**row) if row and row["player_id"] is not None else None


def list_stats(
    conn: Any, *, year: int | None, team: str | None, player_id: int | None,
    position: str | None, min_goals: int | None, sort: str | None,
    limit: int, offset: int,
) -> Page[PlayerStatOut]:
    clauses, params = [], []
    if year is not None:
        clauses.append("t.year = %s")
        params.append(year)
    if team:
        clauses.append("tm.normalized_name = %s")
        params.append(canonical_team_name(team))
    if player_id is not None:
        # Expand to every row sharing this player's name (see list_players) so a
        # player's per-tournament breakdown spans all their editions, not just one.
        clauses.append(
            "p.normalized_name = (select normalized_name from players where id = %s)"
        )
        params.append(player_id)
    if position:
        clauses.append("p.position = %s")
        params.append(position)
    if min_goals is not None:
        clauses.append("s.goals >= %s")
        params.append(min_goals)
    where = ("where " + " and ".join(clauses)) if clauses else ""

    order = "s.goals desc nulls last, p.full_name"
    if sort:
        desc = sort.startswith("-")
        key = sort[1:] if desc else sort
        col = _STAT_SORT_COLUMNS.get(key)
        if col:
            order = f"{col} {'desc' if desc else 'asc'} nulls last, p.full_name"

    base_from = """
        from player_tournament_stats s
        join players p on p.id = s.player_id
        join tournaments t on t.id = s.tournament_id
        left join teams tm on tm.id = s.team_id
    """
    total = _scalar(conn, f"select count(*) {base_from} {where}", tuple(params))
    rows = conn.execute(
        f"""
        select s.player_id, p.full_name as player_name, tm.name as team_name,
               t.year, s.jersey_number, s.goals, s.assists, s.minutes_played,
               s.fouls_committed, s.yellow_cards, s.red_cards, s.appearances
        {base_from} {where}
        order by {order} limit %s offset %s
        """,
        (*params, limit, offset),
    ).fetchall()
    return Page(items=[PlayerStatOut(**r) for r in rows], total=total, limit=limit, offset=offset)


def leaderboard(conn: Any, year: int, metric: str, limit: int) -> list[LeaderboardEntryOut]:
    """Top-N players by goals or assists for one tournament."""
    column = {"scorers": "s.goals", "assists": "s.assists"}[metric]
    rows = conn.execute(
        f"""
        select s.player_id, p.full_name as player_name, tm.name as team_name,
               {column} as value
        from player_tournament_stats s
        join players p on p.id = s.player_id
        join tournaments t on t.id = s.tournament_id
        left join teams tm on tm.id = s.team_id
        where t.year = %s and {column} is not null
        order by {column} desc, p.full_name
        limit %s
        """,
        (year, limit),
    ).fetchall()
    return [
        LeaderboardEntryOut(rank=i + 1, **r) for i, r in enumerate(rows)
    ]
