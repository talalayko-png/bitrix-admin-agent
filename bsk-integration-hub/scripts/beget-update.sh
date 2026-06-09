#!/usr/bin/env bash
# BSK Integration Hub — update an already-bootstrapped Beget VPS to latest main.
#
# Used by the GitHub Actions auto-deploy (piped over SSH). Run as root.
# Idempotent and SAFE: it does NOT modify .env (so your secrets / mode settings
# are preserved), does not delete data, and never enables real API/write mode.
# Requires a prior bootstrap with scripts/beget-deploy.sh.

set -euo pipefail

TARGET="${TARGET:-/opt/bitrix-admin-agent}"
PROJ="${TARGET}/bsk-integration-hub"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "== update $(date -u +%FT%TZ) =="

if [ ! -d "${TARGET}/.git" ]; then
  echo "ERROR: репозиторий не найден в ${TARGET}. Сначала выполните bootstrap (scripts/beget-deploy.sh)." >&2
  exit 1
fi

# Fetch and hard-reset to origin/main. .env is gitignored/untracked, so it is
# preserved by reset --hard.
git -C "${TARGET}" fetch --prune origin
git -C "${TARGET}" reset --hard origin/main

cd "${PROJ}"
if [ ! -f .env ]; then
  echo "ERROR: .env отсутствует. Сначала выполните bootstrap (scripts/beget-deploy.sh)." >&2
  exit 1
fi

# Rebuild + restart (app applies Alembic migrations on startup). .env untouched.
${COMPOSE} up -d --build
${COMPOSE} ps

echo "== health =="
curl -fsS http://localhost:8000/health || true
echo
echo "== update done =="
