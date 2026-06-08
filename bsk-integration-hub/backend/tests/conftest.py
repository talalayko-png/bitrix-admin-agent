"""Test fixtures.

Every test runs against a fresh temporary SQLite database, in ``sync`` queue
mode with mock connectors and dry-run enabled — no network, no Redis, no worker.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch) -> Iterator[None]:
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("QUEUE_BACKEND", "sync")
    monkeypatch.setenv("USE_MOCK_CONNECTORS", "true")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("ALLOW_REAL_API", "false")
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    monkeypatch.setenv("APPROVAL_REQUIRED_FOR", "order_delete,invoice_void")
    monkeypatch.setenv("WORKER_MAX_RETRIES", "3")
    monkeypatch.setenv("WORKER_BACKOFF_BASE_SECONDS", "1")
    monkeypatch.setenv("WORKER_BACKOFF_MAX_SECONDS", "5")

    from src.config import reload_settings
    from src.db.base import init_db, reset_engine

    reload_settings()
    reset_engine()
    init_db()
    yield
    reset_engine()


@pytest.fixture
def client() -> Iterator:
    from fastapi.testclient import TestClient

    from src.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
