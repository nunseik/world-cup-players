"""ESPN parser tests against a real saved fixture (2022 scoring page)."""

from pathlib import Path

from world_cup.sources.espn import parse_leaderboards

FIXTURES = Path(__file__).parent / "fixtures"
SCORING_2022 = (FIXTURES / "espn_scoring_2022.html").read_text()


def test_parses_goals_and_assists_merged_by_player():
    stats = {s.player.full_name: s for s in parse_leaderboards(SCORING_2022, 2022)}

    # Top scorer: Mbappé, 8 goals, 7 games (France).
    mbappe = stats["Kylian Mbappé"]
    assert mbappe.goals == 8
    assert mbappe.appearances == 7
    assert mbappe.team.name == "France"
    assert mbappe.source == "espn"

    # Messi appears in BOTH leaderboards -> merged into one row.
    messi = stats["Lionel Messi"]
    assert messi.goals == 7
    assert messi.assists == 3
    assert messi.team.name == "Argentina"

    # ESPN has no minutes/fouls/jersey at player level.
    assert mbappe.minutes_played is None
    assert mbappe.fouls_committed is None
    assert mbappe.jersey_number is None


def test_ignores_team_level_discipline_table():
    # A country name must never be parsed as a player.
    stats = parse_leaderboards(SCORING_2022, 2022)
    names = {s.player.full_name for s in stats}
    assert "Argentina" not in names
    assert "France" not in names
