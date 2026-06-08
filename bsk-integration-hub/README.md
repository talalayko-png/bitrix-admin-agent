# BSK Integration Hub

Интеграционный хаб **Bitrix24 ↔ МойСклад**: принимает события из обеих систем,
ставит операции в очередь, прогоняет их через настраиваемые бизнес-процессы
(workflow) и даёт админ-панель для наблюдения, dry-run, повторов и ручного
подтверждения операций.

> ⚠️ **Безопасность прежде всего.** В текущем MVP проект **не делает реальных
> вызовов** к Bitrix24 и МойСклад. По умолчанию включены `DRY_RUN=true`,
> `USE_MOCK_CONNECTORS=true` и `ALLOW_REAL_API=false` — коннекторы работают на
> моках, любые «записи» только планируются и логируются. Реальные вызовы
> требуют осознанного включения трёх флагов одновременно и заполнения секретов
> в `.env`. См. [SECURITY.md](./SECURITY.md).

## Что умеет MVP

- **Входящие вебхуки** Bitrix24 и МойСклад с проверкой HMAC-подписи.
- **Очередь операций** на Redis/RQ: воркер, ретраи с экспоненциальным backoff,
  защита от параллельного исполнения одной операции (Redis-лок + `UNIQUE` в БД).
- **Идемпотентность**: повторный вебхук об одном и том же событии не создаёт
  дубликат операции.
- **Workflow-движок** с примером `deal_to_order` (сделка Б24 → заказ МС).
- **Approval gate**: операции из «опасного» списка уходят в статус
  `awaiting_approval` и ждут ручного подтверждения через админку.
- **Snapshots**: для каждой операции сохраняется планируемое «было/стало».
- **Admin API + рабочая admin-панель** (React + Vite): дашборд, очередь, ошибки,
  журнал, связки сущностей, настройки workflow, dry-run, повтор, подтверждение,
  плейсхолдер AI-ассистента, health.
- **Тонкий bitrix24-app** (iframe): статус синхронизации прямо в карточке.

## Структура

```
bsk-integration-hub/
├── backend/            # FastAPI + RQ воркер + доменная логика (Python)
│   ├── src/
│   │   ├── api/        # admin API + входящие вебхуки
│   │   ├── connectors/ # Bitrix24 / МойСклад (mock + guarded real)
│   │   ├── db/         # SQLAlchemy модели и репозитории
│   │   ├── domain/     # доменные сущности и enum'ы
│   │   ├── queue/      # Redis/RQ: enqueue, jobs, locks
│   │   ├── services/   # операции, маппинг, идемпотентность, approval, snapshots
│   │   └── workflows/  # движок и конкретные процессы
│   └── tests/          # pytest на моках (без сети)
├── frontend/
│   ├── admin-panel/    # React + Vite + TS — рабочая панель
│   ├── bitrix24-app/   # тонкий iframe-виджет для карточки Б24
│   └── moysklad-app/   # задел (см. ROADMAP)
├── docs/               # API, workflow, деплой
├── docker-compose.yml  # app + worker + redis + postgres
└── .env.example
```

Подробнее — [ARCHITECTURE.md](./ARCHITECTURE.md).

## Быстрый старт (Docker)

```bash
cp .env.example .env
# отредактируйте ADMIN_API_TOKEN в .env
docker compose up --build
```

- API: http://localhost:8000 (Swagger: http://localhost:8000/docs)
- Admin-панель (dev): см. ниже
- Health: http://localhost:8000/api/admin/health

## Быстрый старт (локально, без Docker, на SQLite)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env          # DRY_RUN=true, QUEUE_BACKEND=sync
export $(grep -v '^#' ../.env | xargs)   # или используйте python-dotenv
uvicorn src.main:app --reload --app-dir .
```

С `QUEUE_BACKEND=sync` операции выполняются прямо в процессе (без Redis/воркера) —
удобно для локальной разработки и тестов. Для реальной очереди поставьте
`QUEUE_BACKEND=redis`, поднимите Redis и запустите воркер:

```bash
python -m src.worker
```

### Admin-панель (React)

```bash
cd frontend/admin-panel
cp .env.example .env        # VITE_API_BASE=http://localhost:8000, VITE_ADMIN_TOKEN=...
npm install
npm run dev                 # http://localhost:5173
```

## Тесты

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Все тесты работают **на моках, без сети и без реального Redis** (используется
`fakeredis` и `QUEUE_BACKEND=sync`).

## Лицензия

[MIT](./LICENSE).
