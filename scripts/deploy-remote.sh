#!/usr/bin/env bash
# Trigger a deploy on the API VM from your laptop (needs the VM ssh key).
# Runs scripts/deploy.sh on the VM over SSH. Override host/key via env:
#   WC_VM_HOST=ubuntu@1.2.3.4 WC_VM_KEY=path/to/key ./scripts/deploy-remote.sh
set -euo pipefail

HOST="${WC_VM_HOST:-ubuntu@136.248.99.64}"
KEY="${WC_VM_KEY:-ssh-keys/ssh-key-2026-03-05.key}"
APP_DIR="${WC_APP_DIR:-/opt/world-cup-players}"

echo "==> deploying to $HOST"
ssh -i "$KEY" -o ConnectTimeout=20 "$HOST" "bash $APP_DIR/scripts/deploy.sh"
