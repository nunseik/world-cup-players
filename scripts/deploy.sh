#!/usr/bin/env bash
# Deploy the latest main to THIS machine (the API VM).
#
# Run on the VM, or remotely from your laptop via scripts/deploy-remote.sh.
# Code-only: it pulls, syncs deps, and restarts the service. It does NOT apply
# database migrations — those need the superuser DSN and are run from a trusted
# machine (the VM's wc_api role has no DDL rights). Apply any new migration with
#   psql "$SUPABASE_DB_URL" -f supabase/migrations/000N_*.sql
# from your laptop BEFORE deploying code that depends on it.
set -euo pipefail

APP_DIR="${WC_APP_DIR:-/opt/world-cup-players}"
UV="${WC_UV:-$HOME/.local/bin/uv}"
SERVICE="${WC_SERVICE:-world-cup-api}"
BRANCH="${WC_BRANCH:-main}"

cd "$APP_DIR"

echo "==> fetching origin/$BRANCH"
git fetch --depth 1 origin "$BRANCH"
OLD=$(git rev-parse --short HEAD)
git reset --hard "origin/$BRANCH"
NEW=$(git rev-parse --short HEAD)
echo "    $OLD -> $NEW"

echo "==> building frontend"
if command -v npm &>/dev/null; then
  # Load VITE_* vars from .env.local (only VITE_ prefix — never exports DB creds)
  if [ -f "$APP_DIR/.env.local" ]; then
    export $(grep '^VITE_' "$APP_DIR/.env.local" | xargs)
  fi
  (cd "$APP_DIR/frontend" && npm ci --prefer-offline && npm run build)
  echo "    frontend built"
else
  echo "    WARN: npm not found — skipping frontend build"
fi

echo "==> uv sync --extra api"
"$UV" sync --extra api

echo "==> restarting $SERVICE"
sudo systemctl restart "$SERVICE"

echo "==> health check"
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health 2>/dev/null || true)
  if [ "$code" = "200" ]; then
    echo "    healthy: $(curl -s http://127.0.0.1:8000/health)"
    echo "==> deployed $NEW"
    exit 0
  fi
  sleep 1
done

echo "ERROR: service not healthy after restart; recent logs:" >&2
sudo journalctl -u "$SERVICE" -n 30 --no-pager >&2
exit 1
