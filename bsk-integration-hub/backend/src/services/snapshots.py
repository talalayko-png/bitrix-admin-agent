"""Snapshot service: records 'before/after' for an operation."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.db.models import Snapshot


class SnapshotService:
    @staticmethod
    def record(
        session: Session,
        operation_id: int,
        entity_ref: str,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> Snapshot:
        snapshot = Snapshot(
            operation_id=operation_id,
            entity_ref=entity_ref,
            action=action,
            before=before,
            after=after,
        )
        session.add(snapshot)
        return snapshot
