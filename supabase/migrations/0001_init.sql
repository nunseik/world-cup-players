-- FIFA World Cup player stats schema.
-- Granularity: tournament totals per player (one row per player per World Cup).
-- All stat fields are nullable: historical tournaments (1970s-1990s) lack
-- minutes/fouls and other modern metrics.

create table if not exists tournaments (
    id            bigint generated always as identity primary key,
    year          int  not null unique,
    host_country  text,
    start_date    date,
    end_date      date,
    num_teams     int,
    source_url    text,
    created_at    timestamptz not null default now()
);

create table if not exists teams (
    id              bigint generated always as identity primary key,
    name            text not null,
    normalized_name text not null unique,
    fifa_code       text,
    confederation   text,
    created_at      timestamptz not null default now()
);

create table if not exists players (
    id              bigint generated always as identity primary key,
    full_name       text not null,
    normalized_name text not null,
    birth_date      date,
    position        text,
    created_at      timestamptz not null default now(),
    -- Best-effort identity: a player is the same across tournaments when the
    -- normalized name matches and birth_date is either equal or unknown.
    -- Postgres treats NULLs as distinct by default, so we coalesce birth_date
    -- to a sentinel in the unique index to dedup name-only matches.
    unique (normalized_name, birth_date)
);

create table if not exists player_tournament_stats (
    id              bigint generated always as identity primary key,
    player_id       bigint not null references players (id) on delete cascade,
    team_id         bigint references teams (id) on delete set null,
    tournament_id   bigint not null references tournaments (id) on delete cascade,
    jersey_number   int,
    goals           int,
    assists         int,
    minutes_played  int,
    fouls_committed int,
    yellow_cards    int,
    red_cards       int,
    appearances     int,
    source          text not null,            -- 'espn' | 'fifa' | 'wikipedia'
    scraped_at      timestamptz not null default now(),
    unique (player_id, tournament_id)
);

create index if not exists idx_pts_tournament on player_tournament_stats (tournament_id);
create index if not exists idx_pts_team       on player_tournament_stats (team_id);

create table if not exists scrape_runs (
    id               bigint generated always as identity primary key,
    year             int,
    source           text not null,
    status           text not null,           -- 'running' | 'success' | 'error'
    records_upserted int not null default 0,
    error            text,
    started_at       timestamptz not null default now(),
    finished_at      timestamptz
);

create index if not exists idx_scrape_runs_year on scrape_runs (year);
