-- API access layer: clients, API keys, and rate-limit counters.
-- Sits alongside the data schema (0001) and powers the read-only HTTP API.
-- Keys are temporary (default 30-day expiry); rate limiting is a per-minute
-- fixed-window counter in Postgres (no Redis), differentiated by client tier.

-- A consumer of the API. Tier lives here (not on the key) so keys can rotate
-- without losing identity or tier. One row per email.
create table if not exists api_clients (
    id          bigint generated always as identity primary key,
    email       text not null unique,
    name        text,
    tier        text not null default 'free',   -- 'free' | 'premium'
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);

-- An issued API token. We store only a SHA-256 hash of the token, never the
-- plaintext: tokens are high-entropy random strings (secrets.token_urlsafe), so
-- a slow password KDF (bcrypt/argon2) buys nothing here. The plaintext is shown
-- to the user exactly once at issue time. key_prefix is the leading few chars,
-- kept in clear for identifying a key in listings without exposing it.
create table if not exists api_keys (
    id           bigint generated always as identity primary key,
    client_id    bigint not null references api_clients (id) on delete cascade,
    key_hash     text not null unique,           -- sha256 hex digest of the token
    key_prefix   text not null,                  -- first ~8 chars, for display only
    created_at   timestamptz not null default now(),
    expires_at   timestamptz not null,           -- created_at + N days (default 30)
    revoked_at   timestamptz,                    -- soft revoke; null = active
    last_used_at timestamptz
);

create index if not exists idx_api_keys_hash   on api_keys (key_hash);
create index if not exists idx_api_keys_client on api_keys (client_id);

-- Per-minute request counters, one row per (key, minute). The rate-limit
-- dependency does an atomic upsert (insert ... on conflict do update ... +1
-- returning count) and compares the result to the tier's limit. Fixed-window
-- semantics: a client may burst up to ~2x the limit across a window boundary —
-- accepted for simplicity (token-bucket via Redis is the upgrade path).
--
-- Rows accumulate; prune old windows out of band, e.g.:
--   delete from api_rate_counters where window_start < now() - interval '1 hour';
create table if not exists api_rate_counters (
    key_id       bigint not null references api_keys (id) on delete cascade,
    window_start timestamptz not null,           -- date_trunc('minute', now())
    count        int not null default 0,
    primary key (key_id, window_start)
);

-- Signup is unauthenticated (the caller has no key yet), so it is rate-limited
-- by client IP instead. Same fixed-window mechanism, keyed on a text IP. This is
-- the known weak spot pending email verification (documented, deliberate).
create table if not exists api_signup_counters (
    ip           text not null,
    window_start timestamptz not null,           -- date_trunc('hour', now())
    count        int not null default 0,
    primary key (ip, window_start)
);
