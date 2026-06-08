.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help install test lint run worker up down fmt frontend

help: ## Показать список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости backend
	cd backend && pip install -r requirements.txt

test: ## Прогнать тесты (на моках, без сети)
	cd backend && pytest -q

lint: ## Проверить ruff (если установлен)
	cd backend && ruff check src tests || true

run: ## Запустить API локально (SQLite, sync-очередь)
	cd backend && uvicorn src.main:app --reload

worker: ## Запустить RQ-воркер (нужен Redis и QUEUE_BACKEND=redis)
	cd backend && python -m src.worker

up: ## docker compose up (app+worker+redis+postgres)
	docker compose up --build

down: ## Остановить docker compose
	docker compose down

frontend: ## Запустить admin-панель (Vite dev server)
	cd frontend/admin-panel && npm install && npm run dev
