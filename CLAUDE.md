# CLAUDE.md

Guidance for Claude Code working in this repo. See [README.md](README.md) for user-facing docs.

## What this is

A headless scraper for **FIFA World Cup player stats** (1970–present) that loads into a
**Supabase/Postgres** database, at **tournament-totals granularity** (one row per player per
World Cup). An API will be built on top later, so the schema and loader are kept clean,
idempotent, and re-runnable.

## Data sources (important — non-obvious history)

- **FBref (Sports Reference) is the primary source.** It has full rosters with minutes, goals,
  assists, cards, **and fouls** (fouls come from a separate "misc" table merged by player+squad).
- **ESPN is a cross-check only.** Its World Cup pages expose *only* Goals/Assists leaderboards at
  player level — no minutes, fouls, or jersey numbers (Discipline is team-level). It was
  evaluated as primary and rejected for this reason.
- **Jersey numbers** aren't in either source's aggregate tables — left null (deferred).
- **Minutes/fouls don't exist for 1970s–1990s** tournaments; those rows are sparse by design
  (all stat columns are nullable).

## FBref + Cloudflare (critical constraint)

FBref is behind **Cloudflare Turnstile, which rejects every Playwright/patchright-launched
browser** — the challenge loops forever and cannot be solved even manually in that browser.
Do **not** try to make a launched/headless browser pass FBref; it will not work.

The working path is **CDP attach to a Chrome the user launches themselves**:
- `world-cup browser` launches the *system* Chrome (not via Playwright) with
  `--remote-debugging-port=9222` and a dedicated profile (`.cache/cdp-chrome`).
- `world-cup scrape --cdp` uses `connect_over_cdp` to drive that genuine browser.
- We never close the user's browser on exit ([browser.py](src/world_cup/browser.py)).

ESPN is **not** Cloudflare-gated and uses the normal patchright-launched browser.

## Architecture

- [models.py](src/world_cup/models.py) — Pydantic models + `normalize_name` (accent/case-folding
  used as the dedup key everywhere).
- [db.py](src/world_cup/db.py) — psycopg upserts. **Every write is an upsert on a natural key**, so
  re-running a year is safe. `coalesce(excluded.x, table.x)` means a later source fills nulls
  without clobbering existing values.
- [browser.py](src/world_cup/browser.py) — CDP-attach OR launch (patchright). Cloudflare-aware.
- [sources/](src/world_cup/sources/) — pluggable adapters implementing `Source.fetch_stats`.
  Parsers are **pure functions** (`build_stats`, `parse_leaderboards`) so they're unit-tested
  against fixtures with no browser/network.
- [pipeline.py](src/world_cup/pipeline.py) — per year: primary → fallback `merge_fill` (by
  normalized player+team) → upsert → record a `scrape_runs` row.
- [tournaments.py](src/world_cup/tournaments.py) — canonical WC editions 1970–2026.
- [supabase/migrations/0001_init.sql](supabase/migrations/0001_init.sql) — schema.

## Conventions

- **Dependency/run management is `uv`.** Run things with `uv run ...`; deps live in
  `pyproject.toml` (dev tools under `[dependency-groups]`, installed by plain `uv sync`).
- **Parsers stay pure and fixture-backed.** When a site's DOM changes, fix the parser and update
  the fixture in `tests/fixtures/`. ESPN's fixture is a real saved page; FBref's mirrors its
  documented `data-stat` schema.
- **Secrets** go in `.env.local` (overrides `.env`; both gitignored). `SUPABASE_DB_URL` is only
  required for DB-backed runs — `--dry-run` never needs it.
- All stat fields are **nullable**; never assume a field exists for older tournaments.

## Common commands

```bash
uv sync                                   # install (incl. dev)
uv run pytest                             # tests (pure, no network)
uv run world-cup scrape --year 2022 --source espn --dry-run   # ESPN, no DB, no Cloudflare
uv run world-cup browser                  # launch real Chrome for FBref
uv run world-cup scrape --year 2022 --cdp # FBref via attached Chrome
psql "$SUPABASE_DB_URL" -f supabase/migrations/0001_init.sql   # apply schema
uv run python scripts/seed_tournaments.py # seed tournaments table
```

## Status / next

Milestones 1–3 done (scaffold, parsers, CDP path). Remaining: live multi-year FBref load to
Supabase, then jersey numbers + legacy (1970–1998) backfill from FBref squad/lineup pages.
Run git commits/pushes only when the user asks.
