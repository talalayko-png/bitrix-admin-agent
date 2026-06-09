from src.db.base import session_scope
from src.db.models import Operation
from src.domain.entities import OperationDraft
from src.services.operations import OperationService


def _run(payload, key="sd-1"):
    op_id = OperationService().create_and_enqueue(
        OperationDraft(
            type="create_supplier_docs",
            source="bitrix24",
            workflow_key="create_supplier_docs",
            idempotency_key=key,
            payload=payload,
        )
    )
    with session_scope() as s:
        op = s.get(Operation, op_id)
        return op_id, op.status, op.result


def test_dry_run_preview_is_complete():
    _, status, result = _run({"entity_type_id": "1030", "item_id": "42", "stage_id": "S1"})
    assert status == "succeeded"
    assert result["dry_run"] is True
    assert result["action"] == "create"

    after = result["after"]
    # received data from B24
    assert after["received"]["item"]["id"] == "42"
    assert after["received"]["product_rows"]
    # required-field validation
    assert after["validation"]["required_ok"] is True
    # mappings resolved
    assert after["mappings"]["organization"]["name"] == "ООО Моя Компания"
    assert after["mappings"]["store"]["name"] == "Основной склад"
    assert after["mappings"]["products"][0]["resolved"] is True
    # documents that would be created
    assert {d["type"] for d in after["documents"]} == {"purchaseorder", "invoicein"}
    assert after["documents"][0]["payload"]["externalCode"] == "b24-1030-42"
    # fields that would be written back to B24
    assert "ufCrm_PO_ID" in after["writeback"]


def test_dry_run_performs_no_writes():
    _, status, result = _run({"entity_type_id": "1030", "item_id": "42"}, key="sd-2")
    assert result["dry_run"] is True
    # apply() never ran -> no created document ids in the result
    assert "purchaseorder" not in result
    assert "invoicein" not in result


def test_idempotent_already_processed_is_noop():
    # item 43 already has MS doc ids written back
    _, status, result = _run({"entity_type_id": "1030", "item_id": "43"}, key="sd-3")
    assert status == "succeeded"
    assert result["action"] == "noop"


def test_operation_idempotency_returns_same_op():
    draft = OperationDraft(
        type="create_supplier_docs",
        source="bitrix24",
        workflow_key="create_supplier_docs",
        idempotency_key="sd-same",
        payload={"entity_type_id": "1030", "item_id": "42"},
    )
    svc = OperationService()
    assert svc.create(draft) == svc.create(draft)
