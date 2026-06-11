"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ----------------------------- responses -----------------------------
class OperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    idempotency_key: str
    type: str
    source: str
    workflow_key: str | None
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    attempts: int
    max_attempts: int
    requires_approval: bool
    approved_by: str | None
    approved_at: datetime | None
    dry_run: bool
    scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    message: str
    data: dict[str, Any] | None
    created_at: datetime


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_ref: str
    action: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


class OperationDetailOut(BaseModel):
    operation: OperationOut
    logs: list[LogOut]
    snapshots: list[SnapshotOut]


class MappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    b24_type: str
    b24_id: str
    ms_type: str
    ms_id: str
    meta: dict[str, Any] | None
    created_at: datetime


class ReferenceMappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    b24_value: str
    ms_type: str
    ms_id: str
    ms_name: str | None
    meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class WorkflowOut(BaseModel):
    key: str
    name: str
    type: str
    trigger_source: str
    enabled: bool
    config: dict[str, Any]
    dry_run_override: bool | None


class DashboardOut(BaseModel):
    counts: dict[str, int]
    flags: dict[str, Any]
    queue_depth: int | None
    recent: list[OperationOut]


# ----------------------------- requests ------------------------------
class ApproveIn(BaseModel):
    approved_by: str | None = None


class MappingIn(BaseModel):
    b24_type: str
    b24_id: str
    ms_type: str
    ms_id: str
    meta: dict[str, Any] | None = None


class WorkflowUpdateIn(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    dry_run_override: bool | None = None


class ReferenceMappingIn(BaseModel):
    kind: str
    b24_value: str
    ms_type: str
    ms_id: str
    ms_name: str | None = None
    meta: dict[str, Any] | None = None


class SimulateDealIn(BaseModel):
    deal_id: str = "1001"
    stage: str = "WON"
    event: str = "deal.update"


class SimulateSmartItemIn(BaseModel):
    entity_type_id: str = "1066"
    item_id: str
    stage_id: str | None = None
    event: str = "item.update"


class AssistantQueryIn(BaseModel):
    question: str = Field(min_length=1)
