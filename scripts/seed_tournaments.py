"""Seed the tournaments table from the canonical static list.

Run standalone:  uv run python scripts/seed_tournaments.py
"""

from __future__ import annotations

from world_cup.db import Database
from world_cup.tournaments import WORLD_CUPS, YEARS


def main() -> None:
    with Database() as db:
        for tournament in WORLD_CUPS:
            db.upsert_tournament(tournament)
    print(f"Seeded {len(WORLD_CUPS)} tournaments ({YEARS[0]}-{YEARS[-1]}).")


if __name__ == "__main__":
    main()
