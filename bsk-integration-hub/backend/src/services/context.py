"""Execution context handed to workflows during execute/plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.config import Settings
from src.connectors.factory import Connectors
from src.db.models import OperationLog
from src.services.mapping import MappingService
from src.services.snapshots import SnapshotService


@dataclass
class ExecutionContext:
    session: Session
    settings: Settings
    connectors: Connectors
    operation_id: int

    def log(self, level: str, message: str, data: dict[str, Any] | None = None) -> None:
        self.session.add(
            OperationLog(
                operation_id=self.operation_id,
                level=level,
                message=message,
                data=data,
            )
        )

    def snapshot(
        self,
        entity_ref: str,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        SnapshotService.record(
            self.session, self.operation_id, entity_ref, action, before, after
        )

    def link(
        self,
        b24_type: str,
        b24_id: str,
        ms_type: str,
        ms_id: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        MappingService.upsert(self.session, b24_type, b24_id, ms_type, ms_id, meta)
