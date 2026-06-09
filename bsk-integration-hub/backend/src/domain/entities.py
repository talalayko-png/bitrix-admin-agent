"""Lightweight domain value objects (not ORM)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebhookEnvelope(BaseModel):
    """Normalized inbound event passed to the workflow engine."""

    source: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    signature_valid: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class OperationDraft(BaseModel):
    """A workflow's proposal to create an operation."""

    type: str
    source: str
    idempotency_key: str
    workflow_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
