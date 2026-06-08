# API

Базовый URL по умолчанию: `http://localhost:8000`.

## Аутентификация

Все эндпоинты `/api/admin/*` требуют admin-токен:

```
Authorization: Bearer <ADMIN_API_TOKEN>
```

(либо заголовок `X-Admin-Token: <ADMIN_API_TOKEN>`).

Вебхуки `/webhooks/*` проверяют HMAC-подпись (заголовок `X-Signature`) при
заданном `*_INBOUND_WEBHOOK_SECRET`.

## Публичные

| Метод | Путь       | Описание                          |
|-------|------------|-----------------------------------|
| GET   | `/health`  | Liveness + флаги безопасности      |
| GET   | `/`        | Информация о сервисе               |
| GET   | `/docs`    | Swagger UI                         |

## Вебхуки

| Метод | Путь                  | Описание                              |
|-------|-----------------------|---------------------------------------|
| POST  | `/webhooks/bitrix24`  | Входящее событие Bitrix24             |
| POST  | `/webhooks/moysklad`  | Входящее событие МойСклад             |

Пример (Bitrix24):

```bash
curl -X POST http://localhost:8000/webhooks/bitrix24 \
  -H 'Content-Type: application/json' \
  -d '{"event":"deal.update","data":{"deal_id":"1001","stage":"WON"}}'
# -> {"event_id": 1, "operation_ids": [1]}
```

## Admin API

| Метод  | Путь                                       | Описание                                  |
|--------|--------------------------------------------|-------------------------------------------|
| GET    | `/api/admin/health`                        | Health + флаги + глубина очереди          |
| GET    | `/api/admin/dashboard`                     | Счётчики, флаги, последние операции       |
| GET    | `/api/admin/settings`                      | Текущие флаги (без секретов)              |
| GET    | `/api/admin/operations?status=&limit=&offset=` | Список операций                       |
| GET    | `/api/admin/operations/{id}`               | Операция + журнал + снимки                |
| GET    | `/api/admin/operations/{id}/logs`          | Журнал операции                           |
| GET    | `/api/admin/operations/{id}/snapshots`     | Снимки «было/стало»                       |
| POST   | `/api/admin/operations/{id}/dry-run`       | Превью (что будет сделано), без записи     |
| POST   | `/api/admin/operations/{id}/retry`         | Повторить (для failed/dead/cancelled)     |
| POST   | `/api/admin/operations/{id}/approve`       | Подтвердить (awaiting_approval)           |
| POST   | `/api/admin/operations/{id}/cancel`        | Отменить                                  |
| GET    | `/api/admin/mappings`                      | Связки сущностей Б24↔МС                   |
| POST   | `/api/admin/mappings`                      | Создать связку                            |
| DELETE | `/api/admin/mappings/{id}`                 | Удалить связку                            |
| GET    | `/api/admin/workflows`                     | Список процессов                          |
| PUT    | `/api/admin/workflows/{key}`               | Вкл/выкл и настройки процесса             |
| POST   | `/api/admin/assistant/query`               | AI-ассистент (плейсхолдер)                |
| POST   | `/api/admin/simulate/deal`                 | Синтетическое событие сделки (демо)       |

Примеры:

```bash
TOKEN=... # ADMIN_API_TOKEN

# Прогнать демо-сделку через процесс
curl -X POST http://localhost:8000/api/admin/simulate/deal \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"deal_id":"1001","stage":"WON"}'

# Посмотреть операции
curl http://localhost:8000/api/admin/operations -H "Authorization: Bearer $TOKEN"

# Превью (dry-run) операции #1
curl -X POST http://localhost:8000/api/admin/operations/1/dry-run \
  -H "Authorization: Bearer $TOKEN"
```

## Статусы операции

`pending → queued → running → succeeded | failed`
с ответвлениями `awaiting_approval` (ждёт подтверждения) и `cancelled`.
`failed`/`dead`/`cancelled` можно повторить вручную (`retry`).
