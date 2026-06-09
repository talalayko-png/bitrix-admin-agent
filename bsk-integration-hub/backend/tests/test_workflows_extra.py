from src.db.base import session_scope
from src.db.models import Operation
from src.domain.entities import OperationDraft
from src.services.operations import OperationService


def _run(draft: OperationDraft):
    op_id = OperationService().create_and_enqueue(draft)
    with session_scope() as s:
        op = s.get(Operation, op_id)
        return op.status, op.result


def test_contact_to_counterparty_dry_run():
    status, result = _run(
        OperationDraft(
            type="contact_to_counterparty",
            source="bitrix24",
            workflow_key="contact_to_counterparty",
            idempotency_key="c-1",
            payload={"contact_id": "55"},
        )
    )
    assert status == "succeeded"
    assert result["dry_run"] is True
    assert result["action"] == "create"
    assert result["after"]["externalCode"] == "55"
    assert result["after"]["name"] == "Иван Петров"


def test_product_sync_dry_run():
    status, result = _run(
        OperationDraft(
            type="product_sync",
            source="bitrix24",
            workflow_key="product_sync",
            idempotency_key="p-1",
            payload={"product_id": "200"},
        )
    )
    assert status == "succeeded"
    assert result["after"]["externalCode"] == "200"
    assert result["after"]["price"] == 120000.0


def test_payment_sync_dry_run():
    status, result = _run(
        OperationDraft(
            type="payment_sync",
            source="bitrix24",
            workflow_key="payment_sync",
            idempotency_key="pay-1",
            payload={"deal_id": "1001", "amount": 5000.0, "key": "1001:5000.0"},
        )
    )
    assert status == "succeeded"
    assert result["action"] == "create"
    assert result["after"]["sum"] == 5000.0


def test_contact_webhook_creates_operation(client, auth):
    res = client.post(
        "/webhooks/bitrix24",
        json={"event": "contact.update", "data": {"contact_id": "55"}},
    ).json()
    assert len(res["operation_ids"]) == 1
    detail = client.get(
        f"/api/admin/operations/{res['operation_ids'][0]}", headers=auth
    ).json()
    assert detail["operation"]["type"] == "contact_to_counterparty"


def test_payment_webhook_creates_operation(client, auth):
    res = client.post(
        "/webhooks/bitrix24",
        json={"event": "payment.add", "data": {"deal_id": "1001", "amount": "5000"}},
    ).json()
    assert len(res["operation_ids"]) == 1
    detail = client.get(
        f"/api/admin/operations/{res['operation_ids'][0]}", headers=auth
    ).json()
    assert detail["operation"]["type"] == "payment_sync"


def test_deal_update_still_single_operation(client):
    """New workflows must not collide with deal_to_order on a plain deal update."""
    res = client.post(
        "/webhooks/bitrix24",
        json={"event": "deal.update", "data": {"deal_id": "1001", "stage": "WON"}},
    ).json()
    assert len(res["operation_ids"]) == 1


def test_workflows_list_has_new(client, auth):
    rows = client.get("/api/admin/workflows", headers=auth).json()
    keys = {r["key"] for r in rows}
    assert {
        "deal_to_order",
        "contact_to_counterparty",
        "product_sync",
        "payment_sync",
    } <= keys
