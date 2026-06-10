#!/usr/bin/env bash
# Read a Bitrix24 smart-process item, its fields and the parent deal, and print a
# human-readable view (field code | title | value) to help map fields to MoySklad.
# Read-only. Run on the server:  bash scripts/inspect-spa.sh <entityTypeId> <itemId>

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

ETID="${1:-}"; ITEM="${2:-}"
if [ -z "$ETID" ] || [ -z "$ITEM" ]; then
  echo "Использование: bash scripts/inspect-spa.sh <entityTypeId> <itemId>"
  echo "Пример:        bash scripts/inspect-spa.sh 1066 481"
  exit 1
fi

TOKEN="$(grep -E '^ADMIN_API_TOKEN=' .env | cut -d= -f2- | tr -d '\r')"
[ -n "$TOKEN" ] || { echo "ADMIN_API_TOKEN не найден в .env"; exit 1; }

URL="http://localhost:8000/api/admin/inspect/smart-process?entity_type_id=${ETID}&item_id=${ITEM}"
echo "Читаю СПА ${ETID}, элемент ${ITEM} ..."
echo

curl -s "$URL" -H "Authorization: Bearer ${TOKEN}" | python3 - <<'PY'
import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print("Ответ не похож на JSON:", e); sys.exit(0)
if "field_overview" not in d:
    print(json.dumps(d, ensure_ascii=False, indent=2)); sys.exit(0)

print("=== ПОЛЯ ЭЛЕМЕНТА СПА (код | название | значение) ===")
for f in d["field_overview"]:
    print(f"{f['code']:<30} | {str(f.get('title') or ''):<42} | {f.get('value')}")

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
    print(f"{k:<30} | {v}")
PY
