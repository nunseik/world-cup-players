# CLAUDE.md

Guidance for Claude Code working in this repo. See [README.md](README.md) for user-facing docs.

## What this is

A headless scraper for **FIFA World Cup player stats** (1970–present) that loads into a
**Supabase/Postgres** database, at **tournament-totals granularity** (one row per player per
World Cup), **plus a read-only HTTP API** (FastAPI) on top of that database. The schema and
loader are kept clean, idempotent, and re-runnable; the API is a separate optional layer (see
**API** below).

## Data sources (important — non-obvious history)

- **FBref (Sports Reference) is the primary source.** It has full rosters with minutes, goals,
  assists, cards, **and fouls** (fouls come from a separate "misc" table merged by player+squad).
- **ESPN is a cross-check only.** Its World Cup pages expose *only* Goals/Assists leaderboards at
  player level — no minutes, fouls, or jersey numbers (Discipline is team-level). It was
  evaluated as primary and rejected for this reason.
- **Jersey numbers** aren't in either source's aggregate tables — left null (deferred).
- **Stat coverage thins out for older tournaments** — rows are sparse by design (all stat columns
  nullable). Observed on FBref: **fouls (and the other detailed misc stats — tackles, interceptions,
  crosses, offsides, pens) begin at 2018**; 2014 and earlier expose only basic discipline
  (yellow/red cards, own goals) in the misc table, though minutes/goals/assists still go back
  further. Each load logs `fbref.fetched … with_fouls=N`, so `with_fouls=0` with no
  `fbref.misc_unavailable` warning means the data is genuinely absent (not a failed fetch).

## FBref + Cloudflare (critical constraint)

FBref is behind **Cloudflare Turnstile, which rejects every Playwright/patchright-launched
browser** — the challenge loops forever and cannot be solved even manually in that browser.
Do **not** try to make a launched/headless browser pass FBref; it will not work.

The working path is **CDP attach to a Chrome the user launches themselves**:
- `world-cup browser` launches the *system* Chrome (not via Playwright) with
  `--remote-debugging-port=9222` and a dedicated profile (`.cache/cdp-chrome`).
- `world-cup scrape --cdp` drives that genuine browser over a **hand-rolled raw-CDP
  client** (`_CDPClient` in [browser.py](src/world_cup/browser.py)) — a thin
  WebSocket talker for CDP protocol 1.3. We do **not** use patchright's
  `connect_over_cdp`: its connect handshake issues a browser-level
  `Browser.setDownloadBehavior` that Chrome 149+ rejects with *"Browser context
  management is not supported"*, aborting the attach before any page loads. Raw CDP
  speaks only `Target`/`Page`/`Runtime` (`get_html` is all the scraper needs), so
  it's immune to that version drift. patchright remains the driver for the
  launched (ESPN) path.
- We never close the user's browser on exit.

ESPN is **not** Cloudflare-gated and uses the normal patchright-launched browser.

## Architecture

- [models.py](src/world_cup/models.py) — Pydantic models + `normalize_name` (accent/case-folding
  used as the dedup key everywhere).
- [db.py](src/world_cup/db.py) — psycopg upserts. **Every write is an upsert on a natural key**, so
  re-running a year is safe. `coalesce(excluded.x, table.x)` means a later source fills nulls
  without clobbering existing values.
- [browser.py](src/world_cup/browser.py) — raw-CDP attach (`_CDPClient`, via `websockets`) OR
  launch (patchright). Cloudflare-aware. Both expose just `get_html(url, wait_for=...)`.
- [sources/](src/world_cup/sources/) — pluggable adapters implementing `Source.fetch_stats`.
  Parsers are **pure functions** (`build_stats`, `parse_leaderboards`) so they're unit-tested
  against fixtures with no browser/network.
- [pipeline.py](src/world_cup/pipeline.py) — per year: primary → fallback `merge_fill` (by
  normalized player+team) → upsert → record a `scrape_runs` row.
- [tournaments.py](src/world_cup/tournaments.py) — canonical WC editions 1970–2026.
- [supabase/migrations/0001_init.sql](supabase/migrations/0001_init.sql) — data schema;
  [0002_api.sql](supabase/migrations/0002_api.sql) — API tables (`api_clients`, `api_keys`,
  `api_rate_counters`, `api_signup_counters`).
- [api/](src/world_cup/api/) — the read API (see **API** below). Separate from the scraper;
  shares config/models but never the `Database` class.

## API (read layer)

Optional FastAPI app under [api/](src/world_cup/api/), installed via the `api` extra
(`uv sync --extra api`) and launched with `world-cup-api` (uvicorn). Read-only public
endpoints over the stats DB; **all `/v1` routes require an API key** (`X-API-Key` or
`Authorization: Bearer`). Keys are temporary (30-day default), tied to a tier (`free`/
`premium`) with **per-minute Postgres fixed-window rate limiting** (no Redis).

Non-obvious design points:
- **Two connection pools** ([api/db.py](src/world_cup/api/db.py)): a `read_only` pool for the
  data endpoints (so the public path physically cannot write) and a small writable pool used
  **only** for auth/rate-limit bookkeeping (`api_keys.last_used_at`, the rate counters, signup
  inserts). Both come from `SUPABASE_DB_URL`.
- **Query functions are pure** ([api/queries.py](src/world_cup/api/queries.py)) — take a
  connection, return response models; unit-tested with fake connections (see
  `tests/conftest.py`), so the suite stays offline like the parser tests. Sorting is
  whitelisted; never interpolate user input as SQL.
- **Response schemas** ([api/schemas.py](src/world_cup/api/schemas.py)) are flat and separate
  from the scraper domain models — keep them decoupled so scraper internals don't leak.
- **Keys are stored as SHA-256 hashes, never plaintext** ([api/keys.py](src/world_cup/api/keys.py));
  `keys.py` is shared by both the public `POST /v1/signup` and the admin CLI
  (`world-cup api-key issue/list/upgrade/revoke`). Signup is IP-rate-limited (no email
  verification yet — the known weak spot; next milestone).

### Deployment (operational — not in the repo)

Live at **`http://136.248.99.64`** on the user's **Oracle Cloud VM** (Ubuntu 24.04, ~950MB RAM).
SSH `ubuntu@136.248.99.64` with `ssh-keys/ssh-key-2026-03-05.key` (gitignored).
- Code at `/opt/world-cup-players`; runs as systemd unit `world-cup-api.service`
  (`uv run world-cup-api --host 127.0.0.1 --port 8000 --workers 2`).
- **Caddy** (system service, `/etc/caddy/Caddyfile`) reverse-proxies `:80 → :8000`, **HTTP only**
  (no domain/TLS yet — add a domain + Caddy auto-TLS for HTTPS).
- **The VM uses a scoped DB role `wc_api`, NOT the superuser** — SELECT on data tables,
  read/write only on `api_*` tables, no DDL. Its DSN is the only credential on the box
  (`/opt/world-cup-players/.env.local`, chmod 600); the superuser DSN stays on the local machine.
- Redeploy: `git -C /opt/world-cup-players pull && uv sync --extra api && sudo systemctl restart world-cup-api`.

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

# API
uv sync --extra api                       # install API deps (FastAPI/uvicorn/psycopg-pool)
psql "$SUPABASE_DB_URL" -f supabase/migrations/0002_api.sql    # apply API tables
uv run world-cup-api --port 8000          # serve locally (http://localhost:8000/docs)
uv run world-cup api-key issue --email x@y.com --tier premium # admin: mint a key
```

## Status / next

Milestones 1–3 done (scaffold, parsers, CDP path). **2022 live-loaded to Supabase** via the
raw-CDP path (FBref 680 + ESPN 82) — schema applied, tournaments seeded, loader verified
idempotent. Remaining:

- **Cross-source merge — fixed.** Two layers now make FBref and ESPN rows line up by team:
  (1) `_team()` in [fbref.py](src/world_cup/sources/fbref.py) strips FBref's glued squad-code
  prefix (`frFrance` → `France`); (2) `canonical_team_name` in [models.py](src/world_cup/models.py)
  maps source name aliases to FBref's form (`South Korea` → `Korea Republic`, `Iran` → `IR Iran`,
  …) and is the team component of both the merge key and the DB dedup key. 2022 now loads 683 rows
  / 32 teams (was 762 / 55 with zero merges). **Residual:** ~3 rows still don't merge due to
  *player-name* spelling differences across sources (`Yahia`/`Yahya`, ESPN `Memphis Depay` vs FBref
  `Memphis`) — needs fuzzy/per-player name matching, deliberately not attempted (false-merge risk).
  Note `players` dedup is `(normalized_name, birth_date)` with null birth_date, so NULLs are
  distinct in Postgres — name-only rows never collapse either (documented in [db.py](src/world_cup/db.py)).
- **Loader speed — fixed.** `upsert_stats_bulk` ([db.py](src/world_cup/db.py)) replaced the per-row
  path with psycopg `executemany(returning=True)`, pipelined into a few round-trips. A year dropped
  from ~5–8 min to ~20s (now dominated by the FBref fetch + 3s inter-page delays, not the write).
  Player ids are mapped back **by position**, not natural key — two distinct same-named players with
  null birth_date (e.g. both Carlos Sánchez in 2018) must keep separate rows. 2018 + 2022 load
  loss-lessly (605 / 683). Re-running a year still duplicates players/stats (null-birth_date
  identity), so truncate the data tables before a clean reload.
- Then: remaining modern years (1994–2014) + 2026, jersey numbers, and legacy (1970–1998) backfill
  from FBref squad/lineup pages.

**API — built and deployed.** Read-only FastAPI layer with API-key auth + tiered rate limiting
(see **API** above), live on the Oracle VM behind Caddy on HTTP. Next on the API:
- **Signup email verification** — `POST /v1/signup` currently issues a key to any email with only
  an IP rate-limit guarding it (no proof of ownership). This is the immediate next milestone.
- Later: HTTPS (needs a domain), `last_used_at` write-throttling, rate-counter cleanup job.

Run git commits/pushes only when the user asks.
