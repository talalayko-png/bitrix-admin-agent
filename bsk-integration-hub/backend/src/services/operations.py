"""Operation lifecycle service: create, enqueue, execute, approve, retry, cancel.

This is the heart of the hub. It enforces idempotency (unique key), the approval
gate, concurrency protection (operation lock), retries with exponential backoff,
and snapshot recording (via workflows).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from src.config import get_settings
from src.connectors.factory import build_connectors
from src.db.base import session_scope
from src.db.models import Operation, OperationLog
from src.db.repositories import find_operation_by_key
from src.domain.entities import OperationDraft
from src.domain.enums import ExecuteResult, OperationStatus
from src.logging_conf import get_logger
from src.queue.enqueue import enqueue_operation
from src.queue.locks import LockNotAcquired, operation_lock
from src.services.approval import dangerous_blocked, needs_approval
from src.services.context import ExecutionContext
from src.utils.backoff import backoff_delay
from src.utils.time import utcnow
from src.workflows.registry import get_workflow

log = get_logger("services.operations")

_RETRYABLE_FROM = {
    OperationStatus.failed.value,
    OperationStatus.dead.value,
    OperationStatus.cancelled.value,
}


@dataclass
class ExecuteOutcome:
    result: ExecuteResult
    retry_delay: int = 0


class OperationService:
    # ------------------------------------------------------------------ create
    def create(self, draft: OperationDraft) -> int:
        """Idempotently create an operation. Returns the operation id."""
        settings = get_settings()
        blocked = dangerous_blocked(settings, draft.type)
        approval = needs_approval(settings, draft.type, draft.requires_approval)
        if blocked:
            status = OperationStatus.blocked
        elif approval:
            status = OperationStatus.awaiting_approval
        else:
            status = OperationStatus.pending
        try:
            with session_scope() as session:
                existing = find_operation_by_key(session, draft.idempotency_key)
                if existing:
                    return existing.id
                op = Operation(
                    idempotency_key=draft.idempotency_key,
                    type=draft.type,
                    source=draft.source,
                    workflow_key=draft.workflow_key,
                    status=status.value,
                    payload=draft.payload,
                    requires_approval=approval,
                    max_attempts=settings.worker_max_retries,
                    dry_run=settings.dry_run,
                    error="dangerous action blocked by policy" if blocked else None,
                )
                session.add(op)
                session.flush()
                op_id = op.id
                session.add(
                    OperationLog(
                        operation_id=op_id,
                        level="warning" if blocked else "info",
                        message=(
                            "Operation blocked: dangerous action disabled by policy"
                            if blocked
                            else f"Operation created (status={status.value}, "
                            f"dry_run={settings.dry_run})"
                        ),
                    )
                )
                return op_id
        except IntegrityError:
            # Lost a race on the unique idempotency key — return the winner.
            with session_scope() as session:
                existing = find_operation_by_key(session, draft.idempotency_key)
                return existing.id if existing else -1

    def enqueue(self, operation_id: int) -> bool:
        """Move a pending operation to queued and schedule it. No-op if the
        operation is awaiting approval or already queued."""
        with session_scope() as session:
            op = session.get(Operation, operation_id)
            if op is None or op.status != OperationStatus.pending.value:
                return False
            op.status = OperationStatus.queued.value
        enqueue_operation(operation_id)
        return True

    def create_and_enqueue(self, draft: OperationDraft) -> int:
        op_id = self.create(draft)
        if op_id > 0:
            self.enqueue(op_id)
        return op_id

    # --------------------------------------------------------------- execution
    def execute(self, operation_id: int) -> ExecuteOutcome:
        """Run a single attempt of an operation (called by worker/sync)."""
        settings = get_settings()

        # phase 1: validate & read idempotency key
        with session_scope() as session:
            op = session.get(Operation, operation_id)
            if op is None:
                return ExecuteOutcome(ExecuteResult.skipped)
            status = OperationStatus(op.status)
            if status.is_terminal or status == OperationStatus.running:
                return ExecuteOutcome(ExecuteResult.skipped)
            if op.requires_approval and op.approved_at is None:
                op.status = OperationStatus.awaiting_approval.value
                return ExecuteOutcome(ExecuteResult.awaiting_approval)
            idem = op.idempotency_key

        # phase 2: execute under the operation lock
        try:
            with operation_lock(settings, idem):
                return self._run_once(operation_id, settings)
        except LockNotAcquired:
            log.info("operation %s already locked by another worker", operation_id)
            return ExecuteOutcome(ExecuteResult.locked)

    def _run_once(self, operation_id: int, settings) -> ExecuteOutcome:
        connectors = build_connectors(settings)
        with session_scope() as session:
            op = session.get(Operation, operation_id)
            if op is None:
                return ExecuteOutcome(ExecuteResult.skipped)

            op.status = OperationStatus.running.value
            op.attempts += 1
            attempt = op.attempts
            session.flush()

            workflow = get_workflow(op.workflow_key or op.type)
            ctx = ExecutionContext(
                session=session,
                settings=settings,
                connectors=connectors,
                operation_id=operation_id,
            )
            if workflow is None:
                op.status = OperationStatus.failed.value
                op.error = f"No workflow registered for '{op.workflow_key or op.type}'"
                ctx.log("error", op.error)
                return ExecuteOutcome(ExecuteResult.failed)

            try:
                result = workflow.execute(ctx, op.payload)
                op.result = result
                op.error = None
                op.status = OperationStatus.succeeded.value
                ctx.log("info", "Operation succeeded")
                return ExecuteOutcome(ExecuteResult.succeeded)
            except Exception as exc:  # noqa: BLE001 - failure is persisted, not raised
                op.error = f"{type(exc).__name__}: {exc}"
                ctx.log("error", f"Attempt {attempt} failed: {op.error}")
                if attempt < op.max_attempts:
                    delay = backoff_delay(
                        attempt,
                        settings.worker_backoff_base_seconds,
                        settings.worker_backoff_max_seconds,
                    )
                    op.status = OperationStatus.queued.value
                    op.scheduled_at = utcnow() + timedelta(seconds=delay)
                    return ExecuteOutcome(ExecuteResult.retry, retry_delay=delay)
                op.status = OperationStatus.failed.value
                return ExecuteOutcome(ExecuteResult.failed)

    # ------------------------------------------------------------- transitions
    def approve(self, operation_id: int, approved_by: str | None) -> bool:
        with session_scope() as session:
            op = session.get(Operation, operation_id)
            if op is None or op.status != OperationStatus.awaiting_approval.value:
                return False
            op.approved_by = approved_by or "admin"
            op.approved_at = utcnow()
            op.status = OperationStatus.queued.value
            session.add(
                OperationLog(
                    operation_id=operation_id,
                    level="info",
                    message=f"Approved by {op.approved_by}",
                )
            )
        enqueue_operation(operation_id)
        return True

    def retry(self, operation_id: int) -> bool:
        with session_scope() as session:
            op = session.get(Operation, operation_id)
            if op is None or op.status not in _RETRYABLE_FROM:
                return False
            op.status = OperationStatus.queued.value
            op.error = None
            op.attempts = 0
            op.scheduled_at = None
            session.add(
                OperationLog(
                    operation_id=operation_id,
                    level="info",
                    message="Manual retry requested",
                )
            )
        enqueue_operation(operation_id)
        return True

    def cancel(self, operation_id: int) -> bool:
        with session_scope() as session:
            op = session.get(Operation, operation_id)
            if op is None:
                return False
            status = OperationStatus(op.status)
            if status.is_terminal or status == OperationStatus.running:
                return False
            op.status = OperationStatus.cancelled.value
            session.add(
                OperationLog(
                    operation_id=operation_id,
                    level="info",
                    message="Operation cancelled",
                )
            )
        return True

    def preview(self, operation_id: int) -> dict:
        """Compute (without writing) what the operation would do — the dry-run
        preview used by the admin panel."""
        settings = get_settings()
        connectors = build_connectors(settings)
        with session_scope() as session:
            op = session.get(Operation, operation_id)
            if op is None:
                raise ValueError("operation not found")
            workflow = get_workflow(op.workflow_key or op.type)
            if workflow is None:
                raise ValueError(f"no workflow for '{op.workflow_key or op.type}'")
            ctx = ExecutionContext(
                session=session,
                settings=settings,
                connectors=connectors,
                operation_id=operation_id,
            )
            plan = workflow.plan(ctx, op.payload)
            return {
                "action": plan.action,
                "entity_ref": plan.entity_ref,
                "before": plan.before,
                "after": plan.after,
                "summary": plan.summary,
            }
