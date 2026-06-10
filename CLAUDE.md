# CLAUDE.md

Guidance for Claude Code when working in this repository.

**Первым делом прочитай `bsk-integration-hub/docs/STATUS.md`** — там текущий
статус проекта, режим безопасности (боевые доступы, dry-run) и активная задача.

## Project

**BSK Integration Hub** — интеграционный хаб Bitrix24 ↔ МойСклад. Код проекта
находится в `bsk-integration-hub/`:

- `backend/` — FastAPI + RQ воркер + доменная логика (Python 3.11)
- `frontend/admin-panel/` — admin-панель (React + Vite + TypeScript)
- `frontend/bitrix24-app/` — тонкий iframe-виджет (vanilla JS)
- `docs/` — API, workflow, деплой

См. `bsk-integration-hub/README.md` и `ARCHITECTURE.md`.

## Команды

```bash
# Backend (из bsk-integration-hub/backend)
pip install -r requirements.txt
pytest -q                       # тесты на моках, без сети
ruff check src tests            # линт
uvicorn src.main:app --reload   # API локально (SQLite, sync-очередь)
python -m src.worker            # RQ-воркер (нужен Redis, QUEUE_BACKEND=redis)

# Frontend (из bsk-integration-hub/frontend/admin-panel)
npm install && npm run dev      # dev-сервер Vite
npm run build                   # прод-сборка
```

## Безопасность

Предохранители: `DRY_RUN`, `USE_MOCK_CONNECTORS`, `ALLOW_REAL_API`
(см. `SECURITY.md`). На проде подключены **боевые** Bitrix24/МойСклад в режиме
«реальные чтения + dry-run» — записи запрещены; не включать запись без явного
подтверждения владельца. Секреты — только в `.env` (в `.gitignore`), никогда
не коммитить.

## Рабочий процесс (предпочтения)

- **Всегда открывать pull request** для изменений — автоматически, без
  дополнительного запроса.
- Вести разработку в feature-ветках, не пушить напрямую в `main`.
- Перед PR: прогонять `pytest` и `ruff` в backend и `npm run build` в admin-панели.
