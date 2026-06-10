#!/usr/bin/env bash
# Read a Bitrix24 smart-process item, its fields and the parent deal, and print a
# human-readable view (field code | title | value) to help map fields to MoySklad.
#
# Read-only. The request runs INSIDE the app container, so it does not depend on
# host port publishing / IPv6 / firewall. If the container is down, the script
# prints the container status and recent logs instead.
#
# Run on the server:  bash scripts/inspect-spa.sh <entityTypeId> <itemId>

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

ETID="${1:-}"; ITEM="${2:-}"
if [ -z "$ETID" ] || [ -z "$ITEM" ]; then
  echo "Использование: bash scripts/inspect-spa.sh <entityTypeId> <itemId>"
  echo "Пример:        bash scripts/inspect-spa.sh 1066 481"
  exit 1
fi

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "Читаю СПА ${ETID}, элемент ${ITEM} (внутри контейнера app) ..."
echo

OUT="$(${COMPOSE} exec -T app python - "$ETID" "$ITEM" 2>/tmp/inspect_spa_err.log <<'PY'
import sys, os, json
try:
    import httpx
except Exception as e:
    print("В контейнере нет httpx:", e); sys.exit(0)

etid, item = sys.argv[1], sys.argv[2]
token = os.environ.get("ADMIN_API_TOKEN", "")
if not token:
    print("ADMIN_API_TOKEN не задан в окружении контейнера app"); sys.exit(0)

try:
    r = httpx.get(
        "http://localhost:8000/api/admin/inspect/smart-process",
        params={"entity_type_id": etid, "item_id": item},
        headers={"Authorization": "Bearer " + token},
        timeout=60,
    )
    raw = r.text
except Exception as e:
    print("Запрос к API внутри контейнера не удался:", e); sys.exit(0)

if r.status_code != 200:
    print("HTTP", r.status_code)

try:
    d = json.loads(raw)
except Exception as e:
    print("Ответ не похож на JSON:", e)
    print(raw[:1500] if raw.strip() else "(пустое тело ответа)")
    sys.exit(0)

if "field_overview" not in d:
    print(json.dumps(d, ensure_ascii=False, indent=2)); sys.exit(0)

print("Режим реальных чтений:", d.get("real_reads_enabled"))
errs = d.get("errors") or {}
if errs:
    print("\n=== ОШИБКИ ВЫЗОВОВ BITRIX24 ===")
    for where, msg in errs.items():
        print(where + ": " + str(msg))

print("\n=== ПОЛЯ ЭЛЕМЕНТА СПА (код | название | значение) ===")
if not d["field_overview"]:
    print("(поля не получены — см. ошибки выше)")
for f in d["field_overview"]:
    print("{:<30} | {:<42} | {}".format(
        f.get("code", ""), str(f.get("title") or ""), f.get("value")))

print("\n=== ТОВАРНЫЕ ПОЗИЦИИ ===")
rows = d.get("product_rows") or []
if not rows:
    print("(нет)")
for p in rows:
    print(json.dumps(p, ensure_ascii=False))

print("\n=== МАТЕРИНСКАЯ СДЕЛКА  id =", d.get("parent_deal_id"), "===")
pd = d.get("parent_deal") or {}
if not pd:
    print("(родительская сделка не найдена; parent-ссылки:", d.get("parent_links"), ")")
for k, v in pd.items():
    print("{:<30} | {}".format(k, v))
PY
)"
RC=$?

if [ "$RC" -ne 0 ] || [ -z "$OUT" ]; then
  echo "Не удалось выполнить запрос внутри контейнера app (код $RC)."
  echo "--- сообщение docker ---"
  cat /tmp/inspect_spa_err.log 2>/dev/null
  echo
  echo "--- статус контейнеров ---"
  ${COMPOSE} ps
  echo
  echo "--- логи app (последние 40 строк) ---"
  ${COMPOSE} logs --tail=40 app
  exit 1
fi

echo "$OUT"
