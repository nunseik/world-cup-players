"""Canonical static list of FIFA World Cup editions, 1970-2026.

Tournaments are a small fixed set, so we keep them here rather than scrape them.
The pipeline/seed script upsert these before loading player stats.
"""

from __future__ import annotations

from datetime import date

from .models import Tournament

WORLD_CUPS: list[Tournament] = [
    Tournament(year=1970, host_country="Mexico", start_date=date(1970, 5, 31), end_date=date(1970, 6, 21), num_teams=16),
    Tournament(year=1974, host_country="West Germany", start_date=date(1974, 6, 13), end_date=date(1974, 7, 7), num_teams=16),
    Tournament(year=1978, host_country="Argentina", start_date=date(1978, 6, 1), end_date=date(1978, 6, 25), num_teams=16),
    Tournament(year=1982, host_country="Spain", start_date=date(1982, 6, 13), end_date=date(1982, 7, 11), num_teams=24),
    Tournament(year=1986, host_country="Mexico", start_date=date(1986, 5, 31), end_date=date(1986, 6, 29), num_teams=24),
    Tournament(year=1990, host_country="Italy", start_date=date(1990, 6, 8), end_date=date(1990, 7, 8), num_teams=24),
    Tournament(year=1994, host_country="United States", start_date=date(1994, 6, 17), end_date=date(1994, 7, 17), num_teams=24),
    Tournament(year=1998, host_country="France", start_date=date(1998, 6, 10), end_date=date(1998, 7, 12), num_teams=32),
    Tournament(year=2002, host_country="South Korea / Japan", start_date=date(2002, 5, 31), end_date=date(2002, 6, 30), num_teams=32),
    Tournament(year=2006, host_country="Germany", start_date=date(2006, 6, 9), end_date=date(2006, 7, 9), num_teams=32),
    Tournament(year=2010, host_country="South Africa", start_date=date(2010, 6, 11), end_date=date(2010, 7, 11), num_teams=32),
    Tournament(year=2014, host_country="Brazil", start_date=date(2014, 6, 12), end_date=date(2014, 7, 13), num_teams=32),
    Tournament(year=2018, host_country="Russia", start_date=date(2018, 6, 14), end_date=date(2018, 7, 15), num_teams=32),
    Tournament(year=2022, host_country="Qatar", start_date=date(2022, 11, 20), end_date=date(2022, 12, 18), num_teams=32),
    Tournament(year=2026, host_country="United States / Canada / Mexico", start_date=date(2026, 6, 11), end_date=date(2026, 7, 19), num_teams=48),
]

YEARS: list[int] = [t.year for t in WORLD_CUPS]
