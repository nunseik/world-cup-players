-- Verification flag for API clients.
-- Email verification isn't built yet, so every self-serve /v1/signup client is
-- unverified. Unverified clients are throttled harder and get smaller pages
-- (enforced in the API layer, not the schema). Admin-issued keys
-- (`world-cup api-key issue`) and `world-cup api-key verify` set this true.
-- Verification is monotonic in code: re-signup never flips a verified client back.
alter table api_clients add column if not exists is_verified boolean not null default false;
