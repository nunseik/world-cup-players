"""Unit tests for normalization and source-merge logic (no network/DB)."""

from world_cup.models import Player, PlayerTournamentStat, Team, normalize_name
from world_cup.pipeline import merge_sources


def test_normalize_name_strips_accents_and_case():
    assert normalize_name("Kylian Mbappé") == "kylian mbappe"
    assert normalize_name("  Özil  ") == "ozil"
    assert normalize_name("Andrés  Iniesta") == "andres iniesta"


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
