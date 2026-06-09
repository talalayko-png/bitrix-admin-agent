# Развёртывание

## Docker Compose (рекомендуется)

```bash
cp .env.example .env
# отредактируйте ADMIN_API_TOKEN
docker compose up --build
```

Поднимаются сервисы:

- `app` — FastAPI (порт 8000);
- `worker` — RQ-воркер (обрабатывает очередь);
- `redis` — брокер очереди;
- `postgres` — БД (по умолчанию в compose `DATABASE_URL` указывает на неё).

Масштабирование воркеров:

```bash
docker compose up --scale worker=3
```

Защита от гонок (Redis-лок + `UNIQUE` в БД) делает несколько воркеров
безопасными — одна операция исполняется только одним воркером.

## Миграции БД (Alembic)

Схема версионируется через Alembic (`backend/alembic/`). В docker-compose
контейнер `app` перед стартом выполняет `alembic upgrade head`, а `worker`
ждёт готовности `app` (healthcheck) — гонок при создании схемы нет.

```bash
cd backend
alembic upgrade head          # применить миграции
alembic downgrade -1          # откатить на одну
alembic revision --autogenerate -m "описание"   # новая миграция из моделей
```

> Для локальной разработки на SQLite и в тестах схема также может создаваться
> через `Base.metadata.create_all` (вызывается в `init_db`) — это удобный
> zero-config путь. Источник истины для прод-схемы — миграции Alembic.

## Локально без Docker

- БД: SQLite (`DATABASE_URL=sqlite:///./data/app.db`, по умолчанию).
- Очередь: `QUEUE_BACKEND=sync` — операции исполняются в процессе, без воркера.

```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload
```

Для реальной очереди локально: поднимите Redis, поставьте `QUEUE_BACKEND=redis`
и запустите `python -m src.worker`.

## Переменные окружения

См. `.env.example`. Ключевые:

| Переменная             | Назначение                                   |
|------------------------|----------------------------------------------|
| `ADMIN_API_TOKEN`      | токен доступа к Admin API (обязателен)        |
| `DATABASE_URL`         | строка подключения к БД                       |
| `QUEUE_BACKEND`        | `sync` или `redis`                            |
| `REDIS_URL`            | адрес Redis                                   |
| `DRY_RUN`              | планировать, но не выполнять записи            |
| `USE_MOCK_CONNECTORS`  | использовать mock-коннекторы (без сети)        |
| `ALLOW_REAL_API`       | главный рубильник исходящих вызовов            |
| `APPROVAL_REQUIRED_FOR`| типы операций, требующих подтверждения         |

## Переход в «реальный» режим (осознанно)

В MVP реальных вызовов нет. Чтобы их включить (после реализации реальных
коннекторов и тестов против песочниц), нужно одновременно:

```
DRY_RUN=false
USE_MOCK_CONNECTORS=false
ALLOW_REAL_API=true
```

и заполнить `BITRIX24_*` / `MOYSKLAD_*` секреты. Пока хотя бы один предохранитель
активен, `guard_egress` блокирует любой исходящий вызов. См. `SECURITY.md`.

## Admin-панель (прод)

```bash
cd frontend/admin-panel
npm install && npm run build      # dist/
```

Раздавайте `dist/` любым статическим сервером (nginx/CDN). Задайте
`VITE_API_BASE` на адрес бэкенда и добавьте origin панели в `CORS_ORIGINS`.
