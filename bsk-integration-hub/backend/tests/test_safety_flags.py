from src.config import reload_settings
from src.db.base import session_scope
from src.db.models import Operation
from src.domain.entities import OperationDraft
from src.services.operations import OperationService


def _status(op_id: int) -> str:
    with session_scope() as s:
        return s.get(Operation, op_id).status


def _draft(type_: str, key: str, **payload) -> OperationDraft:
    return OperationDraft(
        type=type_,
        source="bitrix24",
        workflow_key=type_,
        idempotency_key=key,
        payload=payload,
    )


def test_global_approval_required_gates_everything(monkeypatch):
    monkeypatch.setenv("APPROVAL_REQUIRED", "true")
    reload_settings()
    op_id = OperationService().create_and_enqueue(
        _draft("deal_to_order", "ga-1", deal_id="1001", stage="WON")
    )
    # even a normally auto-executed op now waits for manual approval
    assert _status(op_id) == "awaiting_approval"


def test_dangerous_action_blocked_by_default():
    # DANGEROUS_ACTIONS_DISABLED defaults to true
    op_id = OperationService().create_and_enqueue(
        OperationDraft(
            type="order_delete", source="admin", idempotency_key="dz-1", payload={}
        )
    )
    with session_scope() as s:
        op = s.get(Operation, op_id)
        assert op.status == "blocked"
        assert "dangerous" in (op.error or "").lower()


def test_dangerous_action_allowed_when_policy_off(monkeypatch):
    monkeypatch.setenv("DANGEROUS_ACTIONS_DISABLED", "false")
    reload_settings()
    op_id = OperationService().create_and_enqueue(
        OperationDraft(
            type="invoice_void", source="admin", idempotency_key="dz-2", payload={}
        )
    )
    # not blocked anymore; it's in APPROVAL_REQUIRED_FOR -> awaiting approval
    assert _status(op_id) == "awaiting_approval"


def test_flags_exposed_in_dashboard(client, auth):
    flags = client.get("/api/admin/dashboard", headers=auth).json()["flags"]
    assert flags["dangerous_actions_disabled"] is True
    assert flags["approval_required"] is False
