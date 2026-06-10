"""Admin API — all endpoints are protected by the admin token."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import (
    ApproveIn,
    AssistantQueryIn,
    DashboardOut,
    LogOut,
    MappingIn,
    MappingOut,
    OperationDetailOut,
    OperationOut,
    ReferenceMappingIn,
    ReferenceMappingOut,
    SimulateDealIn,
    SnapshotOut,
    WorkflowOut,
    WorkflowUpdateIn,
)
from src.api.security import require_admin
from src.config import get_settings
from src.connectors.factory import build_connectors
from src.db import repositories as repo
from src.db.models import WorkflowConfig
from src.services.mapping import MappingService
from src.services.operations import OperationService
from src.services.reference_mapping import KINDS, ReferenceMappingService
from src.services.webhooks import WebhookService
from src.utils.time import utcnow
from src.workflows.registry import all_workflows, get_workflow

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

operations_service = OperationService()


def _flags() -> dict[str, Any]:
    s = get_settings()
    return {
        "app_env": s.app_env,
        "dry_run": s.dry_run,
        "use_mock_connectors": s.use_mock_connectors,
        "allow_real_api": s.allow_real_api,
        "real_reads_enabled": s.real_reads_enabled,
        "real_writes_enabled": s.real_writes_enabled,
        "real_api_enabled": s.real_api_enabled,
        "queue_backend": s.queue_backend,
        "approval_required": s.approval_required,
        "approval_required_for": sorted(s.approval_required_set),
        "dangerous_actions_disabled": s.dangerous_actions_disabled,
    }


@router.get("/inspect/smart-process")
def inspect_smart_process(
    entity_type_id: str = Query(..., description="Bitrix24 smart-process entityTypeId"),
    item_id: str = Query(..., description="Bitrix24 smart-process item id"),
) -> dict[str, Any]:
    """Read a smart-process item, its field definitions, product rows and (if
    linked) the parent deal — to map Bitrix24 fields to MoySklad documents.

    Read-only: requires real-reads mode to hit the live portal.

    Each Bitrix24 call is isolated: a failure in one (e.g. product rows) is
    captured under ``errors`` instead of failing the whole request, so the
    field codes we need for mapping still come through, and the underlying
    Bitrix24 error text is surfaced as JSON instead of an opaque 500."""
    settings = get_settings()
    b24 = build_connectors(settings).bitrix24

    errors: dict[str, str] = {}

    def safe(label: str, fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except Exception as exc:  # surface B24 errors as JSON, never 500
            detail = str(exc)
            resp = getattr(exc, "response", None)
            if resp is not None:
                try:
                    detail = f"HTTP {resp.status_code}: {resp.text[:800]}"
                except Exception:  # pragma: no cover - defensive
                    pass
            errors[label] = detail
            return None

    item = safe("get_item", b24.get_item, entity_type_id, item_id) or {}
    fields = safe("get_item_fields", b24.get_item_fields, entity_type_id) or {}
    products = safe("get_item_products", b24.get_item_products, entity_type_id, item_id) or []

    # Parent deal in Bitrix24 smart processes is exposed as `parentId2`
    # (2 = deal entityTypeId). Collect all parent links for visibility.
    parent_links = {
        k: v for k, v in item.items() if k.lower().startswith("parentid") and v
    }
    parent_deal_id = None
    for k, v in item.items():
        if k.lower() == "parentid2" and str(v) not in ("", "0"):
            parent_deal_id = str(v)
    parent_deal = (
        safe("get_deal", b24.get_deal, parent_deal_id) if parent_deal_id else None
    )

    # Compact "code | title | value" view for easy field mapping.
    field_overview = []
    for code, meta in (fields or {}).items():
        title = meta.get("title") if isinstance(meta, dict) else None
        field_overview.append(
            {"code": code, "title": title, "value": item.get(code)}
        )

    return {
        "entity_type_id": entity_type_id,
        "item_id": item_id,
        "real_reads_enabled": settings.real_reads_enabled,
        "errors": errors,
        "field_overview": field_overview,
        "item": item,
        "fields": fields,
        "product_rows": products,
        "parent_links": parent_links,
        "parent_deal_id": parent_deal_id,
        "parent_deal": parent_deal,
    }


def _queue_depth() -> int | None:
    s = get_settings()
    if s.queue_backend != "redis":
        return 0
    try:
        from rq import Queue

        from src.queue.connection import get_redis

        return Queue(s.queue_name, connection=get_redis()).count
    except Exception:  # pragma: no cover - redis optional
        return None


# --------------------------------------------------------------- dashboard
@router.get("/health")
def admin_health() -> dict[str, Any]:
    return {"status": "ok", "flags": _flags(), "queue_depth": _queue_depth()}


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)) -> DashboardOut:
    recent = repo.list_operations(db, limit=10)
    return DashboardOut(
        counts=repo.count_by_status(db),
        flags=_flags(),
        queue_depth=_queue_depth(),
        recent=[OperationOut.model_validate(op) for op in recent],
    )


@router.get("/settings")
def get_settings_view() -> dict[str, Any]:
    """Non-secret view of current configuration flags."""
    s = get_settings()
    return {
        **_flags(),
        "worker_max_retries": s.worker_max_retries,
        "worker_backoff_base_seconds": s.worker_backoff_base_seconds,
        "worker_backoff_max_seconds": s.worker_backoff_max_seconds,
        "operation_lock_ttl_seconds": s.operation_lock_ttl_seconds,
        "assistant_enabled": s.assistant_enabled,
    }


# -------------------------------------------------------------- operations
@router.get("/operations", response_model=list[OperationOut])
def list_operations(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[OperationOut]:
    ops = repo.list_operations(db, status=status_filter, limit=limit, offset=offset)
    return [OperationOut.model_validate(op) for op in ops]


@router.get("/operations/{operation_id}", response_model=OperationDetailOut)
def operation_detail(
    operation_id: int, db: Session = Depends(get_db)
) -> OperationDetailOut:
    op = repo.get_operation(db, operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail="operation not found")
    return OperationDetailOut(
        operation=OperationOut.model_validate(op),
        logs=[LogOut.model_validate(x) for x in repo.operation_logs(db, operation_id)],
        snapshots=[
            SnapshotOut.model_validate(x)
            for x in repo.operation_snapshots(db, operation_id)
        ],
    )


@router.get("/operations/{operation_id}/logs", response_model=list[LogOut])
def operation_logs(operation_id: int, db: Session = Depends(get_db)) -> list[LogOut]:
    return [LogOut.model_validate(x) for x in repo.operation_logs(db, operation_id)]


@router.get("/operations/{operation_id}/snapshots", response_model=list[SnapshotOut])
def operation_snapshots(
    operation_id: int, db: Session = Depends(get_db)
) -> list[SnapshotOut]:
    return [
        SnapshotOut.model_validate(x)
        for x in repo.operation_snapshots(db, operation_id)
    ]


@router.post("/operations/{operation_id}/retry")
def retry_operation(operation_id: int) -> dict[str, Any]:
    if not operations_service.retry(operation_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="operation cannot be retried in its current state",
        )
    return {"ok": True}


@router.post("/operations/{operation_id}/approve")
def approve_operation(operation_id: int, body: ApproveIn) -> dict[str, Any]:
    if not operations_service.approve(operation_id, body.approved_by):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="operation is not awaiting approval",
        )
    return {"ok": True}


@router.post("/operations/{operation_id}/cancel")
def cancel_operation(operation_id: int) -> dict[str, Any]:
    if not operations_service.cancel(operation_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="operation cannot be cancelled in its current state",
        )
    return {"ok": True}


@router.post("/operations/{operation_id}/dry-run")
def dry_run_operation(operation_id: int) -> dict[str, Any]:
    try:
        return operations_service.preview(operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------- mappings
@router.get("/mappings", response_model=list[MappingOut])
def list_mappings(db: Session = Depends(get_db)) -> list[MappingOut]:
    return [MappingOut.model_validate(m) for m in MappingService.list(db)]


@router.post("/mappings", response_model=MappingOut, status_code=201)
def create_mapping(body: MappingIn, db: Session = Depends(get_db)) -> MappingOut:
    link = MappingService.upsert(
        db, body.b24_type, body.b24_id, body.ms_type, body.ms_id, body.meta
    )
    db.commit()
    db.refresh(link)
    return MappingOut.model_validate(link)


@router.delete("/mappings/{mapping_id}", status_code=204)
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)) -> None:
    if not MappingService.delete(db, mapping_id):
        raise HTTPException(status_code=404, detail="mapping not found")
    db.commit()


# ----------------------------------------------------- reference mappings
@router.get("/reference-mappings", response_model=list[ReferenceMappingOut])
def list_reference_mappings(
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ReferenceMappingOut]:
    rows = ReferenceMappingService.list(db, kind=kind)
    return [ReferenceMappingOut.model_validate(r) for r in rows]


@router.post("/reference-mappings", response_model=ReferenceMappingOut, status_code=201)
def upsert_reference_mapping(
    body: ReferenceMappingIn, db: Session = Depends(get_db)
) -> ReferenceMappingOut:
    if body.kind not in KINDS:
        raise HTTPException(
            status_code=422, detail=f"kind must be one of {sorted(KINDS)}"
        )
    row = ReferenceMappingService.upsert(
        db, body.kind, body.b24_value, body.ms_type, body.ms_id, body.ms_name, body.meta
    )
    db.commit()
    db.refresh(row)
    return ReferenceMappingOut.model_validate(row)


@router.delete("/reference-mappings/{mapping_id}", status_code=204)
def delete_reference_mapping(mapping_id: int, db: Session = Depends(get_db)) -> None:
    if not ReferenceMappingService.delete(db, mapping_id):
        raise HTTPException(status_code=404, detail="reference mapping not found")
    db.commit()


# --------------------------------------------------------------- workflows
@router.get("/workflows", response_model=list[WorkflowOut])
def list_workflows(db: Session = Depends(get_db)) -> list[WorkflowOut]:
    configs = {
        c.key: c for c in db.execute(select(WorkflowConfig)).scalars().all()
    }
    result: list[WorkflowOut] = []
    for wf in all_workflows():
        cfg = configs.get(wf.key)
        result.append(
            WorkflowOut(
                key=wf.key,
                name=wf.name,
                type=wf.type,
                trigger_source=wf.trigger_source,
                enabled=cfg.enabled if cfg else True,
                config=cfg.config if cfg else {},
                dry_run_override=cfg.dry_run_override if cfg else None,
            )
        )
    return result


@router.put("/workflows/{key}", response_model=WorkflowOut)
def update_workflow(
    key: str, body: WorkflowUpdateIn, db: Session = Depends(get_db)
) -> WorkflowOut:
    wf = get_workflow(key)
    if wf is None:
        raise HTTPException(status_code=404, detail="unknown workflow")
    cfg = db.execute(
        select(WorkflowConfig).where(WorkflowConfig.key == key)
    ).scalar_one_or_none()
    if cfg is None:
        cfg = WorkflowConfig(
            key=wf.key,
            name=wf.name,
            trigger_source=wf.trigger_source,
            enabled=True,
            config={},
        )
        db.add(cfg)
    if body.enabled is not None:
        cfg.enabled = body.enabled
    if body.config is not None:
        cfg.config = body.config
    if body.dry_run_override is not None:
        cfg.dry_run_override = body.dry_run_override
    cfg.updated_at = utcnow()
    db.commit()
    db.refresh(cfg)
    return WorkflowOut(
        key=wf.key,
        name=wf.name,
        type=wf.type,
        trigger_source=wf.trigger_source,
        enabled=cfg.enabled,
        config=cfg.config,
        dry_run_override=cfg.dry_run_override,
    )


# --------------------------------------------------------------- assistant
@router.post("/assistant/query")
def assistant_query(body: AssistantQueryIn) -> dict[str, Any]:
    s = get_settings()
    return {
        "enabled": s.assistant_enabled,
        "question": body.question,
        "answer": (
            "AI-ассистент пока не подключён (плейсхолдер). Здесь появятся "
            "объяснения ошибок синхронизации, подсказки по маппингу сущностей "
            "и генерация правил workflow."
        ),
    }


# ---------------------------------------------------------------- simulate
@router.post("/simulate/deal")
def simulate_deal(body: SimulateDealIn) -> dict[str, Any]:
    """Inject a synthetic Bitrix24 deal event (no real Bitrix24 needed) so the
    full pipeline can be exercised from the admin panel."""
    result = WebhookService().handle(
        source="bitrix24",
        event_type=body.event,
        payload={"deal_id": body.deal_id, "stage": body.stage},
        signature_valid=True,
    )
    return result
