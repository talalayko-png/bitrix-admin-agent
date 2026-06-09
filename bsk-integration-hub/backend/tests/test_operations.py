from src.db.base import session_scope
from src.db.models import Operation
from src.db.repositories import (
    list_operations,
    operation_logs,
    operation_snapshots,
)
from src.domain.entities import OperationDraft
from src.services.operations import OperationService


def _draft(key="deal_to_order:1001:WON", **over):
    base = dict(
        type="deal_to_order",
        source="bitrix24",
        workflow_key="deal_to_order",
        idempotency_key=key,
        payload={"deal_id": "1001", "stage": "WON"},
    )
    base.update(over)
    return OperationDraft(**base)


def test_create_and_execute_dry_run():
    svc = OperationService()
    op_id = svc.create_and_enqueue(_draft())
    assert op_id > 0
    with session_scope() as s:
        op = s.get(Operation, op_id)
        assert op.status == "succeeded"
        assert op.dry_run is True
        assert op.result["dry_run"] is True
        assert op.result["action"] == "create"
        assert op.attempts == 1
        snaps = operation_snapshots(s, op_id)
        logs = operation_logs(s, op_id)
    assert len(snaps) == 1
    assert snaps[0].action == "create"
    assert any("DRY-RUN" in log.message for log in logs)


def test_idempotent_create():
    svc = OperationService()
    id1 = svc.create(_draft(key="same-key"))
    id2 = svc.create(_draft(key="same-key"))
    assert id1 == id2
    with session_scope() as s:
        assert len(list_operations(s, limit=100)) == 1


def test_approval_gate_via_draft_flag():
    svc = OperationService()
    op_id = svc.create_and_enqueue(_draft(key="approve-1", requires_approval=True))
    with session_scope() as s:
        op = s.get(Operation, op_id)
        assert op.status == "awaiting_approval"
        assert op.requires_approval is True
        assert op.result is None  # not executed yet

    assert svc.approve(op_id, "tester") is True
    with session_scope() as s:
        op = s.get(Operation, op_id)
        assert op.status == "succeeded"
        assert op.approved_by == "tester"


def test_approval_required_by_type(monkeypatch):
    # order_delete is dangerous; disable that policy here to test the approval gate
    monkeypatch.setenv("DANGEROUS_ACTIONS_DISABLED", "false")
    from src.config import reload_settings

    reload_settings()
    svc = OperationService()
    op_id = svc.create_and_enqueue(
        OperationDraft(
            type="order_delete",  # in APPROVAL_REQUIRED_FOR
            source="admin",
            idempotency_key="del-1",
            payload={},
        )
    )
    with session_scope() as s:
        assert s.get(Operation, op_id).status == "awaiting_approval"


def test_unknown_workflow_fails_then_manual_retry():
    svc = OperationService()
    op_id = svc.create_and_enqueue(
        OperationDraft(
            type="totally_unknown",
            source="admin",
            idempotency_key="u-1",
            payload={},
        )
    )
    with session_scope() as s:
        op = s.get(Operation, op_id)
        assert op.status == "failed"
        assert "No workflow" in (op.error or "")

    assert svc.retry(op_id) is True
    with session_scope() as s:
        op = s.get(Operation, op_id)
        assert op.status == "failed"
        assert op.attempts == 1  # reset to 0, then one fresh attempt


def test_retries_exhaust_with_backoff(monkeypatch):
    from src.workflows.deal_to_order import DealToOrderWorkflow

    def boom(self, ctx, payload):
        raise RuntimeError("transient boom")

    monkeypatch.setattr(DealToOrderWorkflow, "plan", boom)

    svc = OperationService()
    op_id = svc.create_and_enqueue(_draft(key="flaky-1"))
    with session_scope() as s:
        op = s.get(Operation, op_id)
        assert op.status == "failed"
        assert op.attempts == 3  # WORKER_MAX_RETRIES
        assert "RuntimeError" in (op.error or "")
        logs = operation_logs(s, op_id)
    assert sum("failed" in log.message for log in logs) >= 3


def test_cancel_pending_like_operation():
    svc = OperationService()
    # awaiting_approval can be cancelled
    op_id = svc.create_and_enqueue(_draft(key="cancel-1", requires_approval=True))
    assert svc.cancel(op_id) is True
    with session_scope() as s:
        assert s.get(Operation, op_id).status == "cancelled"
    # cannot retry-approve a cancelled op via approve
    assert svc.approve(op_id, "x") is False
