# World Cup Players Scraper

Headless scraper for FIFA World Cup player stats (1970–present) → Supabase/Postgres.

- **Primary source: FBref (Sports Reference)** — full rosters with minutes, goals,
  assists, cards, **and fouls**. Covers all World Cups (goals/appearances back to 1970;
  minutes/fouls for the modern era).
- **Cross-check source: ESPN** (2002+) — Goals/Assists leaderboards only. Used to
  corroborate and fill FBref's goals/assists.

Data is stored at **tournament-totals granularity** (one row per player per World Cup).
All stat fields are nullable — older tournaments don't record minutes/fouls, and jersey
numbers aren't in either source's aggregate tables.

> **FBref is behind Cloudflare Turnstile, which rejects *any* automated browser**
> (a Playwright-launched Chrome loops forever and can't be solved even by hand).
> The working path is to **attach to a real Chrome you launch yourself** over the
> DevTools protocol — that browser isn't automation-fingerprinted, so Turnstile
> validates normally. Use `world-cup browser` + `scrape --cdp` (see below).
> ESPN is not Cloudflare-gated and works via the normal launched browser.

## Setup

```bash
uv sync                              # install dependencies
# FBref needs the real Chrome channel (default). Install Google Chrome, OR set
# SCRAPE_BROWSER_CHANNEL="" to use the bundled browser:
uv run patchright install chromium   # bundled fallback browser
cp .env.example .env                 # then fill in SUPABASE_DB_URL
```

`SUPABASE_DB_URL` comes from your Supabase project → **Project Settings → Database →
Connection string** (direct or session pooler).

### Apply the schema

```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/0001_init.sql
uv run python scripts/seed_tournaments.py
```

## Scraping FBref (Cloudflare): attach to your own Chrome

FBref's Cloudflare Turnstile blocks automated browsers. Drive a Chrome you launch
yourself instead:

```bash
# 1. Launch your real Chrome with a DevTools port (opens FBref). Solve the
#    Cloudflare challenge once if it appears, and leave the window open:
uv run world-cup browser

# 2. In another terminal, scrape by attaching to that Chrome:
uv run world-cup scrape --year 2022 --cdp
```

`--cdp` defaults to `http://localhost:9222`; pass a URL to override, or set
`SCRAPE_CDP_URL` in `.env`. The launched Chrome uses a dedicated profile
(`.cache/cdp-chrome`) so it won't collide with your everyday browser.

ESPN (`--source espn`) needs none of this — it runs through the normal browser.

## Usage

```bash
# Parse + print, no DB needed:
uv run world-cup scrape --year 2022 --dry-run

# Scrape and load one year:
uv run world-cup scrape --year 2022

# All seeded years:
uv run world-cup scrape

# Pick a single source (default is "both" = FBref primary + ESPN cross-check):
uv run world-cup scrape --year 2022 --source fbref
uv run world-cup scrape --year 2022 --source espn
```

## API

A read-only HTTP API (FastAPI) serves the loaded data. It's an optional install:

```bash
uv sync --extra api
psql "$SUPABASE_DB_URL" -f supabase/migrations/0002_api.sql   # API tables (keys, rate limits)
uv run world-cup-api --port 8000                              # add --reload for dev
```

Open `http://localhost:8000/docs` for interactive Swagger docs.

**Auth — API keys.** Every `/v1` endpoint requires a key, sent as `X-API-Key: <token>`
(or `Authorization: Bearer <token>`). Keys are **temporary** (default 30-day expiry) and
tied to a tier (`free` / `premium`). Users get one via self-serve signup:

```bash
curl -XPOST localhost:8000/v1/signup -H 'content-type: application/json' \
  -d '{"email":"you@example.com"}'        # returns a free key, shown once
```

Admins manage keys from the CLI (runs with DB credentials):

```bash
uv run world-cup api-key issue   --email you@example.com --tier premium
uv run world-cup api-key upgrade --email you@example.com --tier premium
uv run world-cup api-key revoke  --prefix wc_AbC12dEf
uv run world-cup api-key list
```

**Rate limiting** is per-tier, per-minute (`free`=60, `premium`=600 by default), enforced
with a Postgres fixed-window counter — no Redis. Over-limit requests get `429` +
`Retry-After`; every response carries `X-RateLimit-Limit` / `-Remaining` headers.

**Endpoints** (all under `/v1`): `tournaments`, `tournaments/{year}`,
`tournaments/{year}/leaderboards/{scorers,assists}`, `players` (search by `q`/`position`/`team`),
`players/{id}`, `players/{id}/career`, `teams`, `stats` (filter by `year`/`team`/`player_id`/
`position`/`min_goals`, sortable). List endpoints return an offset-paginated
`{items, total, limit, offset}` envelope.

## Layout

| Path | Purpose |
|------|---------|
| `src/world_cup/models.py` | Pydantic domain models + name normalization |
| `src/world_cup/db.py` | Idempotent upserts (safe to re-run) |
| `src/world_cup/browser.py` | Cloudflare-aware undetected browser (patchright) |
| `src/world_cup/sources/fbref.py` | Primary adapter — full rosters incl. minutes/fouls |
| `src/world_cup/sources/espn.py` | Cross-check adapter — goals/assists leaderboards |
| `src/world_cup/pipeline.py` | Scrape → merge → load orchestration |
| `src/world_cup/tournaments.py` | Canonical WC editions 1970–2026 |
| `src/world_cup/api/` | Read-only HTTP API (FastAPI): keys, rate limits, queries, routers |
| `supabase/migrations/` | Schema SQL (`0001` data, `0002` API) |

## Tests

```bash
uv run pytest
```

Parser tests run against saved HTML fixtures in `tests/fixtures/` (deterministic, no network).
ESPN's fixture is a real saved page; FBref's mirrors its documented `data-stat` schema.

## Status

- [x] Milestone 1 — scaffold + schema
- [x] Milestone 2 — ESPN parser (verified live) + FBref primary adapter (unit-tested)
- [ ] Milestone 3 — live multi-year validation + DB load (needs unblocked network + `SUPABASE_DB_URL`)
- [ ] Milestone 4 — jersey numbers + legacy (1970–1998) backfill from FBref squad/lineup pages

## Known limitations

- **FBref is Cloudflare-gated** and rejects automated browsers — scrape it via
  `world-cup browser` + `scrape --cdp` (attaching to your own Chrome).
- **Jersey numbers** aren't in either source's aggregate stat tables — deferred (Milestone 4).
- **Minutes/fouls don't exist** for 1970s–1990s tournaments; those rows stay sparse by design.
