"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.admin.router import router as admin_router
from src.api.webhooks.router import router as webhooks_router
from src.config import get_settings
from src.db.base import init_db
from src.logging_conf import setup_logging
from src.seed import seed_workflows
from src.utils.time import utcnow


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    seed_workflows()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BSK Integration Hub",
        version=__version__,
        summary="Bitrix24 <-> MoySklad integration hub",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(webhooks_router)
    app.include_router(admin_router)

    @app.get("/health")
    def health() -> dict[str, Any]:
        s = get_settings()
        return {
            "status": "ok",
            "dry_run": s.dry_run,
            "real_api_enabled": s.real_api_enabled,
            "queue_backend": s.queue_backend,
            "time": utcnow().isoformat(),
        }

    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "name": "bsk-integration-hub",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
            "admin_api": "/api/admin",
        }

    return app


app = create_app()
