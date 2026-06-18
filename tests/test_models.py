"""Unit tests for normalization and source-merge logic (no network/DB)."""

from world_cup.models import (
    Player,
    PlayerTournamentStat,
    Team,
    canonical_team_name,
    normalize_name,
)
from world_cup.pipeline import merge_sources


def test_normalize_name_strips_accents_and_case():
    assert normalize_name("Kylian Mbappé") == "kylian mbappe"
    assert normalize_name("  Özil  ") == "ozil"
    assert normalize_name("Andrés  Iniesta") == "andres iniesta"


def test_canonical_team_name_maps_source_aliases():
    # ESPN names resolve to FBref's canonical form (both normalized).
    assert canonical_team_name("South Korea") == canonical_team_name("Korea Republic")
    assert canonical_team_name("Iran") == canonical_team_name("IR Iran")
    assert canonical_team_name("Republic of Ireland") == canonical_team_name("Rep. of Ireland")
    assert canonical_team_name("USA") == "united states"
    # Names with no alias pass straight through normalize_name.
    assert canonical_team_name("France") == "france"


def test_merge_matches_across_team_alias():
    # Same player, FBref "Korea Republic" vs ESPN "South Korea" -> one merged row.
    primary = _stat("Son Heung-Min", team="Korea Republic", minutes_played=300, source="fbref")
    fallback = _stat("Son Heung-Min", team="South Korea", goals=2, source="espn")

    merged = merge_sources([primary], [fallback])
    assert len(merged) == 1
    assert merged[0].minutes_played == 300  # FBref kept
    assert merged[0].goals == 2             # filled from ESPN across the alias


def _stat(name, team="Argentina", **kw):
    return PlayerTournamentStat(
        year=2022, player=Player(full_name=name), team=Team(name=team),
        source=kw.pop("source", "espn"), **kw,
    )


def test_merge_fill_only_fills_nulls():
    primary = _stat("Lionel Messi", goals=7, minutes_played=None, source="espn")
    fallback = _stat("Lionel Messi", goals=99, minutes_played=690, source="fifa")

    merged = merge_sources([primary], [fallback])
    assert len(merged) == 1
    s = merged[0]
    assert s.goals == 7              # primary value kept
    assert s.minutes_played == 690   # null filled from fallback
    assert s.source == "espn"


def test_merge_appends_unmatched_fallback_rows():
    primary = _stat("Lionel Messi", goals=7)
    fallback = _stat("Emiliano Martinez", minutes_played=690, source="fifa")

    merged = merge_sources([primary], [fallback])
    names = {m.player.full_name for m in merged}
    assert names == {"Lionel Messi", "Emiliano Martinez"}
