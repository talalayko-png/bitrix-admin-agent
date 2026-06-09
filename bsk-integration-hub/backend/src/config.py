"""Application configuration via environment / .env (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_env: str = "dev"
    app_name: str = "bsk-integration-hub"
    log_level: str = "INFO"
    log_json: bool = False

    # --- Egress safety fuses (all three must be flipped for real calls) ---
    dry_run: bool = True
    use_mock_connectors: bool = True
    allow_real_api: bool = False

    # --- Admin API ---
    admin_api_token: str = "change-me-please-generate-a-long-random-token"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    # --- Database ---
    database_url: str = "sqlite:///./data/app.db"

    # --- Queue (Redis / RQ) ---
    queue_backend: str = "sync"  # sync | redis
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "operations"
    worker_max_retries: int = 5
    worker_backoff_base_seconds: int = 2
    worker_backoff_max_seconds: int = 300
    operation_lock_ttl_seconds: int = 300

    # --- Approval gate ---
    approval_required_for: str = "order_delete,invoice_void"

    # --- Bitrix24 (real mode only) ---
    bitrix24_base_url: str = ""
    bitrix24_outbound_webhook_url: str = ""
    bitrix24_inbound_webhook_secret: str = ""

    # --- MoySklad (real mode only) ---
    moysklad_base_url: str = "https://api.moysklad.ru/api/remap/1.2"
    moysklad_token: str = ""
    moysklad_inbound_webhook_secret: str = ""

    # --- AI assistant (placeholder) ---
    assistant_enabled: bool = False
    assistant_provider: str = ""
    assistant_api_key: str = ""

    # ----- derived helpers -----
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def approval_required_set(self) -> set[str]:
        return {x.strip() for x in self.approval_required_for.split(",") if x.strip()}

    @property
    def real_api_enabled(self) -> bool:
        """Real outbound calls are allowed ONLY when all three fuses agree."""
        return self.allow_real_api and not self.use_mock_connectors and not self.dry_run

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Clear the cache and rebuild settings (used by tests after env changes)."""
    get_settings.cache_clear()
    return get_settings()
