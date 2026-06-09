# CLAUDE.md

Guidance for Claude Code when working in this repository.

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

В MVP реальных вызовов к Bitrix24/МойСклад нет: предохранители `DRY_RUN`,
`USE_MOCK_CONNECTORS`, `ALLOW_REAL_API` (см. `SECURITY.md`). Секреты — только в
`.env` (в `.gitignore`), никогда не коммитить.

## Рабочий процесс (предпочтения)

- **Всегда открывать pull request** для изменений — автоматически, без
  дополнительного запроса.
- Вести разработку в feature-ветках, не пушить напрямую в `main`.
- Перед PR: прогонять `pytest` и `ruff` в backend и `npm run build` в admin-панели.
