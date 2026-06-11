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

    # --- Supplier-docs workflow (Bitrix24 smart process -> MoySklad) ---
    supplier_docs_entity_type_id: int = 0          # B24 smart-process typeId (0 = any)
    supplier_docs_target_stage: str = ""           # target stageId ("" = any stage)
    bitrix24_writeback_purchaseorder_field: str = ""  # B24 UF field for MS purchaseorder id
    bitrix24_writeback_invoicein_field: str = ""      # B24 UF field for MS invoicein id
    bitrix24_writeback_supply_field: str = ""         # B24 UF field for MS supply link

    # UF-коды полей СПА «Снабжение» (портал basht, entityTypeId=1066;
    # выписаны инспектором с элемента 481) — переопределяются через .env
    # «Плановая дата готовности у поставщика»
    supplier_docs_field_ready_date: str = "ufCrm19_1771861585"
    # «Дата оплаты поставщику»
    supplier_docs_field_payment_date: str = "ufCrm19_1771861774"
    # «№ и дата счёта поставщика»
    supplier_docs_field_invoice_ref: str = "ufCrm19_1771512153"
    # «Склад МС» в материнской сделке: iblock_element (список Б24 №193),
    # значение — id элемента списка; сопоставление со складом МС — через
    # reference-mappings (kind=store, b24_value=<id элемента>)
    supplier_docs_deal_store_field: str = "UF_CRM_1695973329"

    # --- MoySklad defaults & client behavior ---
    moysklad_default_organization: str = ""        # org name/id (resolved via mapping/lookup)
    moysklad_default_store: str = ""               # store name/id
    moysklad_max_retries: int = 4
    moysklad_backoff_base_seconds: float = 0.5
    moysklad_page_limit: int = 100

    # --- Global safety toggles ---
    approval_required: bool = False           # if true, EVERY operation needs manual approval
    dangerous_actions_disabled: bool = True   # if true, dangerous op types are blocked entirely
    app_base_url: str = ""

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
    def real_reads_enabled(self) -> bool:
        """Real *reads* from Bitrix24/MoySklad are allowed when real connectors
        are on. This permits 'real reads + dry-run' (preview against live data,
        no writes)."""
        return self.allow_real_api and not self.use_mock_connectors

    @property
    def real_writes_enabled(self) -> bool:
        """Real *writes* additionally require dry-run to be off — i.e. all three
        fuses agree."""
        return self.real_reads_enabled and not self.dry_run

    @property
    def real_api_enabled(self) -> bool:
        """Backwards-compatible alias: equals ``real_writes_enabled``."""
        return self.real_writes_enabled

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
