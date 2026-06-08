"""Workflow engine: turns inbound events into queued operations."""

from __future__ import annotations

from sqlalchemy import select

from src.db.base import session_scope
from src.db.models import WorkflowConfig
from src.domain.entities import WebhookEnvelope
from src.logging_conf import get_logger
from src.services.operations import OperationService
from src.workflows.registry import all_workflows

log = get_logger("services.engine")


class WorkflowEngine:
    def __init__(self) -> None:
        self.operations = OperationService()

    def process(self, envelope: WebhookEnvelope) -> list[int]:
        enabled = self._enabled_map()
        operation_ids: list[int] = []
        for workflow in all_workflows():
            if not enabled.get(workflow.key, True):
                continue
            if not workflow.matches(envelope):
                continue
            draft = workflow.build_draft(envelope)
            if draft is None:
                continue
            op_id = self.operations.create_and_enqueue(draft)
            operation_ids.append(op_id)
            log.info("workflow %s -> operation %s", workflow.key, op_id)
        return operation_ids

    @staticmethod
    def _enabled_map() -> dict[str, bool]:
        with session_scope() as session:
            rows = session.execute(select(WorkflowConfig)).scalars().all()
            return {row.key: row.enabled for row in rows}
