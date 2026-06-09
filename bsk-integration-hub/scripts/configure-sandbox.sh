#!/usr/bin/env bash
# Interactive sandbox configuration helper.
#
# Asks for the Bitrix24 / MoySklad sandbox values, writes them into .env, switches
# the service to SAFE 'real reads + dry-run' mode (no writes), and restarts.
# Run on the server:  bash scripts/configure-sandbox.sh

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1   # -> bsk-integration-hub
ENV=".env"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

[ -f "$ENV" ] || { echo "ОШИБКА: $ENV не найден. Сначала разверни сервис (beget-deploy.sh)."; exit 1; }

mask() { local v="$1"; [ ${#v} -le 8 ] && echo "****" || echo "${v:0:4}...${v: -4}"; }

set_kv() {
  local key="$1"; shift; local val="$*"
  grep -v "^${key}=" "$ENV" > "$ENV.tmp" && mv "$ENV.tmp" "$ENV"
  printf '%s=%s\n' "$key" "$val" >> "$ENV"
}

echo "=============================================================="
echo " Настройка песочницы Bitrix24 / МойСклад (реальные ЧТЕНИЯ, БЕЗ записи)"
echo " Вставляй значения и жми Enter. Чтобы прервать — Ctrl+C."
echo "=============================================================="
echo
echo "--- МойСклад ---"
read -r -p "1) Токен доступа МойСклад: " MS_TOKEN
read -r -p "2) Название организации (как в МС): " MS_ORG
read -r -p "3) Название склада (как в МС): " MS_STORE
echo
echo "--- Bitrix24 ---"
read -r -p "4) Ссылка входящего вебхука (https://...bitrix24.ru/rest/.../.../): " B24_URL
read -r -p "5) application_token исходящего вебхука: " B24_TOKEN

echo
echo "=============================================================="
echo " Проверь, всё ли верно:"
echo "   Организация МС : $MS_ORG"
echo "   Склад МС       : $MS_STORE"
echo "   Токен МС       : $(mask "$MS_TOKEN")"
echo "   Вебхук Б24 URL : $B24_URL"
echo "   Токен Б24      : $(mask "$B24_TOKEN")"
echo "   Режим          : реальные ЧТЕНИЯ + dry-run (записи ВЫКЛ)"
echo "=============================================================="
read -r -p "Применить и перезапустить сервис? (y/n): " ANS
[ "$ANS" = "y" ] || [ "$ANS" = "Y" ] || { echo "Отменено. .env не изменён."; exit 0; }

# --- значения ---
set_kv MOYSKLAD_TOKEN "$MS_TOKEN"
set_kv MOYSKLAD_DEFAULT_ORGANIZATION "$MS_ORG"
set_kv MOYSKLAD_DEFAULT_STORE "$MS_STORE"
set_kv BITRIX24_OUTBOUND_WEBHOOK_URL "$B24_URL"
set_kv BITRIX24_INBOUND_WEBHOOK_SECRET "$B24_TOKEN"

# --- безопасный режим: реальные чтения, но БЕЗ записей и опасных действий ---
set_kv ALLOW_REAL_API true
set_kv USE_MOCK_CONNECTORS false
set_kv DRY_RUN true
set_kv DANGEROUS_ACTIONS_DISABLED true

echo
echo "Применяю и перезапускаю..."
${COMPOSE} up -d

echo
echo "=============================================================="
echo " Готово. Режим: реальные ЧТЕНИЯ + dry-run (записи заблокированы)."
echo " Проверка:"
echo "   1) В админ-панели на дашборде должен быть ЖЁЛТЫЙ баннер"
echo "      'Реальные ЧТЕНИЯ + dry-run'."
echo "   2) В тестовом Bitrix24 измени любую СДЕЛКУ — через секунды"
echo "      в разделе 'Операции' появится операция с предпросмотром"
echo "      (что было бы создано в МойСклад). Записей в МС при этом нет."
echo "=============================================================="
