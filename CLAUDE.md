# CLAUDE.md

Guidance for Claude Code working in this repo. See [README.md](README.md) for user-facing docs.

## What this is

A headless scraper for **FIFA World Cup player stats** (1970–present) that loads into a
**self-hosted Postgres** database on the Oracle Cloud VM, at **tournament-totals granularity**
(one row per player per World Cup), **plus a read-only HTTP API** (FastAPI) and a **React
frontend** on top of that database. The schema and loader are kept clean, idempotent, and
re-runnable; the API and frontend are separate optional layers (see **API** and **Frontend** below).

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

**Cloudflare also blocks Oracle Cloud datacenter IPs** (confirmed: `curl` from the VM returns
403 from Cloudflare). FBref scraping must always run from a residential/office network — the
Oracle VM can only run ESPN-only scrapes.

## Architecture

- [models.py](src/world_cup/models.py) — Pydantic models + `normalize_name` (accent/case-folding
  used as the dedup key everywhere).
- [db.py](src/world_cup/db.py) — psycopg upserts. **Every write is an upsert on a natural key**, so
  re-running a year is safe. `coalesce(excluded.x, table.x)` means a later source fills nulls
  without clobbering existing values.
- [browser.py](src/world_cup/browser.py) — raw-CDP attach (`_CDPClient`, via `websockets`) OR
  launch (patchright). Cloudflare-aware. Both expose just `get_html(url, wait_for=...)`.
  On Linux, `--no-sandbox --disable-dev-shm-usage` are added automatically so patchright
  works inside VMs/containers without user namespaces.
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
- [scripts/refresh_year.py](scripts/refresh_year.py) — atomic ESPN-only reload of one year:
  scrapes first, then in a single transaction deletes old stats + orphaned players and inserts
  fresh rows. Used by the cron job on the VM. A failed scrape rolls back, leaving old data intact.
- [frontend/](frontend/) — React SPA (see **Frontend** below).

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
  inserts). The write pool uses `SUPABASE_DB_URL`; the read pool uses `API_READ_ONLY_DB_URL`
  if set, otherwise falls back to `SUPABASE_DB_URL`.
- **Query functions are pure** ([api/queries.py](src/world_cup/api/queries.py)) — take a
  connection, return response models; unit-tested with fake connections (see
  `tests/conftest.py`), so the suite stays offline like the parser tests. Sorting is
  whitelisted; never interpolate user input as SQL.
- **Query-time player dedup by `normalized_name`.** Because `birth_date` is uniformly null,
  the `(normalized_name, birth_date)` identity splits every multi-tournament player into one
  row per edition (Messi = 6 rows). The API papers over this at read time without touching data:
  `list_players` groups by `normalized_name` (one search result per person, returning a
  representative `min(id)`); `career_aggregates` and `list_stats?player_id=` re-expand that id to
  **all** rows sharing its `normalized_name`, so career totals and per-tournament breakdowns span
  every edition. Trade-off: two genuinely different people with the same normalized name collapse
  in the view (accepted; the real fix is backfilling `birth_date`). This dedup is read-only and
  reversible — the underlying duplicate rows are untouched.
- **Response schemas** ([api/schemas.py](src/world_cup/api/schemas.py)) are flat and separate
  from the scraper domain models — keep them decoupled so scraper internals don't leak.
- **Keys are stored as SHA-256 hashes, never plaintext** ([api/keys.py](src/world_cup/api/keys.py));
  `keys.py` is shared by both the public `POST /v1/signup` and the admin CLI
  (`world-cup api-key issue/list/upgrade/revoke`). Signup is IP-rate-limited (no email
  verification yet — the known weak spot; next milestone).

## Frontend

React SPA under [frontend/](frontend/) built with **Vite + TypeScript + Tailwind CSS v4**.
Phase 1 of a sticker-album app — currently a single "album" view with player cards as stickers,
plus a stats table view. Intended to evolve into an unofficial FIFA World Cup sticker album interface.

Key design points:
- **Two views**: sticker album (phase 1) and stats table (fallback). Album view is the primary
  interface, showing players grouped by team in a collectable card format.
- **Sticker album** ([frontend/src/components/AlbumPage.tsx](frontend/src/components/AlbumPage.tsx)):
  - Player cards with front (photo + position) and back (stats) rendered via 3D CSS transforms
  - Wikipedia API integration for player photos (batch-fetched, cached in memory)
  - Collected/duplicate tracking persisted to localStorage (`wc_album_v1`)
  - Dark/light theme auto-detects system preference (`window.matchMedia('(prefers-color-scheme: dark)')`)
    and updates automatically when system preference changes
  - Header scrolls naturally with content (not sticky) to maximize mobile screen space
  - Year selector shows tournament host countries (abbreviated, e.g. USA/CAN/MEX)
  - Default year is 2022, progress bar shows collection percentage
- **Stats table view**: filters by year/team/position/sort, player search via name/team autocomplete,
  slide-in career panel.
- **API client** ([frontend/src/api.ts](frontend/src/api.ts)): thin typed `fetch` wrapper —
  no axios or react-query. Five methods covering tournaments, player search, stats, and career.
- **API key** (`VITE_API_KEY`) is baked into the JS bundle at build time. Use a dedicated
  `free`-tier key — never an admin key. Key is read-only and rate-limited so bundle exposure
  is acceptable. The frontend key (issued 2026-06-19, expires 2026-07-19) is stored in
  `.env.local` on both the laptop and the VM.
- **Dev proxy**: Vite proxies `/v1` → `http://136.248.99.64` in dev so CORS is never an issue
  locally. In prod, Caddy routes `/v1/*` directly to `:8000`.

Non-obvious gotcha:
- `export $(grep '^VITE_' .env.local | xargs)` is used in `deploy.sh` to export VITE vars
  before the build. `source <()` process substitution does **not** work in non-interactive SSH
  sessions (the CD pipeline's shell), so always use the `export $(xargs)` form.

### Local frontend dev

```bash
cd frontend
npm install                    # first time only
# create frontend/.env.local with: VITE_API_KEY=wc_xxxxx
npm run dev                    # http://localhost:5173 (proxies /v1 to live VM)
npm run build                  # outputs to frontend/dist/
```

### Deployment (operational — not in the repo)

Live at **`http://136.248.99.64`** on the user's **Oracle Cloud VM** (Ubuntu 24.04, ~950MB RAM,
2 GB swap). SSH `ubuntu@136.248.99.64` with `ssh-keys/ssh-key-2026-03-05.key` (gitignored).
- Code at `/opt/world-cup-players`; runs as systemd unit `world-cup-api.service`
  (`uv run world-cup-api --host 127.0.0.1 --port 8000 --workers 2`).
- **Caddy** (system service, `/etc/caddy/Caddyfile`) serves the React SPA at `/` from
  `frontend/dist/` and proxies `/v1/*`, `/docs*`, `/openapi.json`, `/health` to `:8000`.
  **HTTP only** (no domain/TLS yet — add a domain + Caddy auto-TLS for HTTPS).
- **Database is self-hosted Postgres 18** on the VM (migrated from Supabase). Two roles:
  - `wc_owner` — full write access on all data tables; used by the scraper and refresh cron.
    DSN: `SUPABASE_DB_URL=postgresql://wc_owner:…@localhost/world_cup`
  - `wc_api` — SELECT on data tables, read/write on `api_*` tables, no DDL; used by the API.
    DSN: `API_READ_ONLY_DB_URL=postgresql://wc_api:…@localhost/world_cup`
  Both DSNs live in `/opt/world-cup-players/.env.local` (chmod 600).
- **Migrations**: apply from the VM as `ubuntu` with `psql "$SUPABASE_DB_URL" -f …` (wc_owner
  has DDL on the world_cup database). No remote superuser needed.
- **CD: every push to `main` auto-deploys** via [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)
  — SSHes into the VM using the `VM_SSH_KEY_B64` repo secret (base64-encoded private key) and runs
  `scripts/deploy.sh` (git reset → frontend build → uv sync → restart → health check).
  `VITE_API_KEY` is sourced from `.env.local` on the VM before the build.
- Manual redeploy from laptop: `./scripts/deploy-remote.sh` (wraps the same `scripts/deploy.sh` over SSH).
- **2026 refresh cron** (ubuntu crontab): `0 0,6,12,18 * * *` runs
  `uv run python scripts/refresh_year.py 2026`, logging to `/var/log/wc-refresh.log`.
  ESPN-only (FBref is blocked by Cloudflare from Oracle IPs). Atomic: scrape → delete old rows
  → insert fresh rows in one transaction; a failed scrape leaves the DB untouched.

## Conventions

- **Dependency/run management is `uv`.** Run things with `uv run ...`; deps live in
  `pyproject.toml` (dev tools under `[dependency-groups]`, installed by plain `uv sync`).
- **Parsers stay pure and fixture-backed.** When a site's DOM changes, fix the parser and update
  the fixture in `tests/fixtures/`. ESPN's fixture is a real saved page; FBref's mirrors its
  documented `data-stat` schema.
- **Secrets** go in `.env.local` (overrides `.env`; both gitignored). `SUPABASE_DB_URL` is only
  required for DB-backed runs — `--dry-run` never needs it. On the VM, `SCRAPE_BROWSER_CHANNEL=`
  (empty) is also set so patchright uses its bundled Chromium instead of system Chrome.
- All stat fields are **nullable**; never assume a field exists for older tournaments.

## Common commands

```bash
uv sync                                   # install (incl. dev)
uv run pytest                             # tests (pure, no network)
uv run world-cup scrape --year 2022 --source espn --dry-run   # ESPN, no DB, no Cloudflare
uv run world-cup browser                  # launch real Chrome for FBref
uv run world-cup scrape --year 2022 --cdp # FBref via attached Chrome
psql "$SUPABASE_DB_URL" -f supabase/migrations/0001_init.sql   # apply schema (run on VM as wc_owner)
uv run python scripts/seed_tournaments.py # seed tournaments table

# API
uv sync --extra api                       # install API deps (FastAPI/uvicorn/psycopg-pool)
psql "$SUPABASE_DB_URL" -f supabase/migrations/0002_api.sql    # apply API tables (run on VM as wc_owner)

# 2026 refresh (runs automatically via cron on VM; also runnable manually)
uv run python scripts/refresh_year.py 2026
uv run world-cup-api --port 8000          # serve locally (http://localhost:8000/docs)
uv run world-cup api-key issue --email x@y.com --tier premium # admin: mint a key

# Frontend
cd frontend && npm run dev                # http://localhost:5173 (proxies /v1 to live VM)
cd frontend && npm run build              # build frontend/dist/ for production
```

## Status / next

**All 15 tournaments loaded (1970–2026), 7 505 rows.** DB is self-hosted Postgres 18 on the
Oracle VM (migrated from Supabase). 2026 is partial (mid-tournament); refreshes every 6 hours
via cron (ESPN-only).

- **Cross-source merge — fixed.** `_team()` strips FBref's glued squad-code prefix; `canonical_team_name`
  maps ESPN aliases to FBref's form. **Residual:** ~30 player-name spelling differences across sources
  (e.g. `Yahia`/`Yahya`, ESPN `Memphis Depay` vs FBref `Memphis`) — fuzzy matching deferred (false-merge risk).
  `players` dedup is `(normalized_name, birth_date)` with null birth_date distinct in Postgres —
  name-only rows never collapse (documented in [db.py](src/world_cup/db.py)).
- **Loader speed — fixed.** `upsert_stats_bulk` uses psycopg `executemany(returning=True)` with
  position-based id mapping; a year loads in ~20s. Re-running a year duplicates players/stats
  (null-birth_date identity) — use `scripts/refresh_year.py` for safe reloads.
- **2026 auto-refresh — live.** ESPN-only cron every 6 hours on the VM. FBref is blocked by
  Cloudflare from Oracle IPs; ESPN gives goals/assists only, which is sufficient for incremental
  updates (FBref-loaded minutes/cards are preserved via `coalesce` upserts).

**API — built and deployed.** Read-only FastAPI layer with API-key auth + tiered rate limiting,
live on the Oracle VM behind Caddy on HTTP.

**Frontend — built and deployed.** React SPA at `http://136.248.99.64/` — sticker album interface
(phase 1) with 2022 as default year, Wikipedia player photos, dark/light theme (auto-follows system
preference), and scrollable header for mobile. Fallback stats table view with filters and player search.
Next for the frontend: album card "gluing" mechanic and sticker set completion rewards.

Next for the backend/infra:
- **Signup email verification** — `POST /v1/signup` currently issues a key to any email with only
  an IP rate-limit guarding it. This is the immediate next milestone.
- Later: HTTPS (needs a domain), `last_used_at` write-throttling, rate-counter cleanup job.
- Jersey numbers and legacy (1970–1998) deep backfill from FBref squad/lineup pages (local only).
- Frontend API key renewal — current key expires 2026-07-19; rotate via
  `world-cup api-key issue`, update `.env.local` on VM, redeploy.

Run git commits/pushes only when the user asks.
