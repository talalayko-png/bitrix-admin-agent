#!/usr/bin/env bash
# BSK Integration Hub — safe first deploy for a clean Beget VPS.
#
# One-liner (run as root on the server):
#   curl -fsSLO https://raw.githubusercontent.com/talalayko-png/bitrix-admin-agent/main/bsk-integration-hub/scripts/beget-deploy.sh
#   bash beget-deploy.sh
#
# SAFE & IDEMPOTENT. First run is mock + dry-run only:
#   DRY_RUN=true, USE_MOCK_CONNECTORS=true, ALLOW_REAL_API=false.
# No real Bitrix24/MoySklad secrets, no real API calls, no write actions.
# Re-running keeps the existing ADMIN_API_TOKEN and does not clobber .env values.
#
# Overridable via env: DOMAIN, ACME_EMAIL, REPO_URL.

set -euo pipefail

DOMAIN="${DOMAIN:-hub.bsk-group.ru}"
ACME_EMAIL="${ACME_EMAIL:-admin@bsk-group.ru}"
REPO_URL="${REPO_URL:-https://github.com/talalayko-png/bitrix-admin-agent.git}"
TARGET="/opt/bitrix-admin-agent"
PROJ="${TARGET}/bsk-integration-hub"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

say() { printf '\n\033[1;34m== %s ==\033[0m\n' "$*"; }

say "1. Проверки окружения"
whoami
git --version
curl --version | head -1
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден — устанавливаю"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi
docker --version
docker compose version

say "2. Утилиты (git curl nano htop ufw ca-certificates openssl)"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y git curl nano htop ufw ca-certificates openssl

say "3. Firewall (22/80/443 открыть, 8000 закрыть)"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 8000/tcp
ufw --force enable
ufw status verbose

say "4. Репозиторий"
if [ -d "${TARGET}/.git" ]; then
  git -C "${TARGET}" pull --ff-only
else
  git clone "${REPO_URL}" "${TARGET}"
fi
cd "${PROJ}"

say "5. .env (без боевых секретов)"
cp -n .env.example .env
set_kv() {
  local k="$1"; shift; local v="$*"
  if grep -qE "^${k}=" .env; then
    sed -i "s|^${k}=.*|${k}=${v}|" .env
  else
    echo "${k}=${v}" >> .env
  fi
}

say "6. ADMIN_API_TOKEN (стабильный при повторных запусках)"
cur="$(grep -E '^ADMIN_API_TOKEN=' .env | cut -d= -f2- || true)"
if [ -z "${cur}" ] || printf '%s' "${cur}" | grep -q 'change-me'; then
  ADMIN="$(openssl rand -hex 32)"
  set_kv ADMIN_API_TOKEN "${ADMIN}"
  echo ">>> НОВЫЙ ADMIN_API_TOKEN (СОХРАНИТЕ): ${ADMIN}"
else
  echo ">>> ADMIN_API_TOKEN уже задан — оставляю прежний"
fi

say "7. Безопасные значения .env"
set_kv APP_ENV production
set_kv DOMAIN "${DOMAIN}"
set_kv APP_BASE_URL "https://${DOMAIN}"
set_kv ACME_EMAIL "${ACME_EMAIL}"
set_kv CORS_ORIGINS "https://${DOMAIN}"
set_kv DATABASE_URL postgresql+psycopg://bsk:bsk@postgres:5432/bsk
set_kv QUEUE_BACKEND redis
set_kv REDIS_URL redis://redis:6379/0
set_kv DRY_RUN true
set_kv USE_MOCK_CONNECTORS true
set_kv ALLOW_REAL_API false
set_kv DANGEROUS_ACTIONS_DISABLED true
set_kv APPROVAL_REQUIRED true
# гарантируем пустые боевые секреты на первом деплое
set_kv BITRIX24_OUTBOUND_WEBHOOK_URL ""
set_kv BITRIX24_INBOUND_WEBHOOK_SECRET ""
set_kv MOYSKLAD_TOKEN ""

say "8. Проверка безопасности .env"
echo "--- предохранители ---"
grep -E '^(DRY_RUN|USE_MOCK_CONNECTORS|ALLOW_REAL_API)=' .env
echo "--- боевые секреты пусты? ---"
if grep -qE '^BITRIX24_OUTBOUND_WEBHOOK_URL=$' .env \
   && grep -qE '^BITRIX24_INBOUND_WEBHOOK_SECRET=$' .env \
   && grep -qE '^MOYSKLAD_TOKEN=$' .env; then
  echo "OK: BITRIX24_*/MOYSKLAD_TOKEN пусты"
else
  echo "ВНИМАНИЕ: проверьте, что секреты пусты!"
fi

say "9. Запуск docker compose (prod + Caddy/HTTPS)"
${COMPOSE} up -d --build

say "10. Контейнеры"
${COMPOSE} ps

say "11. Логи (хвост)"
${COMPOSE} logs --tail=80 app || true
${COMPOSE} logs --tail=80 caddy || true

say "12. Health"
echo "internal:"; curl -s http://localhost:8000/health || true; echo
echo "https://${DOMAIN}:"; curl -s "https://${DOMAIN}/health" || echo "(пусто/ошибка — проверьте DNS A-запись и логи caddy)"; echo

say "Готово"
echo "Если https не ответил: убедитесь, что A-запись ${DOMAIN} -> IP сервера, и:"
echo "  ${COMPOSE} logs --tail=120 caddy"
echo "  ${COMPOSE} restart caddy"
