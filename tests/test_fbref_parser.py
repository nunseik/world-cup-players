"""FBref parser tests against a faithful fixture (data-stat schema).

NOTE: the fixture mirrors FBref's documented `data-stat` table structure (the
misc table is HTML-commented to mimic FBref hiding secondary tables). Live DOM
validation must be run from a non-datacenter network — FBref is Cloudflare-gated.
"""

from pathlib import Path

from world_cup.sources.fbref import build_stats, parse_table

FIXTURES = Path(__file__).parent / "fixtures"
STANDARD = (FIXTURES / "fbref_standard_sample.html").read_text()
MISC = (FIXTURES / "fbref_misc_sample.html").read_text()


def test_parse_table_skips_repeated_header_rows():
    rows = parse_table(STANDARD, "stats_standard")
    names = [r["player"] for r in rows]
    assert names == ["Lionel Messi", "Kylian Mbappé"]  # the class="thead" row is skipped


def test_parse_table_uncomments_hidden_misc_table():
    rows = parse_table(MISC, "stats_misc")  # table is inside an HTML comment
    assert {r["player"] for r in rows} == {"Lionel Messi", "Kylian Mbappé"}


def test_build_stats_maps_fields_and_enriches_fouls():
    stats = {s.player.full_name: s for s in build_stats(STANDARD, MISC, 2022)}

    messi = stats["Lionel Messi"]
    assert messi.team.name == "Argentina"
    assert messi.minutes_played == 690
    assert messi.goals == 7
    assert messi.assists == 3
    assert messi.appearances == 7
    assert messi.yellow_cards == 1
    assert messi.fouls_committed == 8       # filled from the misc table
    assert messi.jersey_number is None      # not available in aggregate tables
    assert messi.source == "fbref"

    mbappe = stats["Kylian Mbappé"]
    assert mbappe.minutes_played == 644
    assert mbappe.goals == 8
    assert mbappe.fouls_committed == 5


def test_build_stats_without_misc_leaves_fouls_null():
    stats = build_stats(STANDARD, None, 2022)
    assert all(s.fouls_committed is None for s in stats)
