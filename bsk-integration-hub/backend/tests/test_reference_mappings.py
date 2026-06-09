from src.db.base import session_scope
from src.domain.entities import OperationDraft
from src.services.operations import OperationService
from src.services.reference_mapping import ReferenceMappingService


def test_reference_mapping_crud(client, auth):
    created = client.post(
        "/api/admin/reference-mappings",
        headers=auth,
        json={
            "kind": "product",
            "b24_value": "200",
            "ms_type": "product",
            "ms_id": "ms-prod-200",
            "ms_name": "Станок",
        },
    )
    assert created.status_code == 201
    mid = created.json()["id"]

    rows = client.get("/api/admin/reference-mappings?kind=product", headers=auth).json()
    assert any(r["id"] == mid for r in rows)

    # upsert is idempotent on (kind, b24_value)
    again = client.post(
        "/api/admin/reference-mappings",
        headers=auth,
        json={"kind": "product", "b24_value": "200", "ms_type": "product", "ms_id": "ms-prod-XXX"},
    )
    assert again.json()["id"] == mid
    assert again.json()["ms_id"] == "ms-prod-XXX"

    assert client.delete(f"/api/admin/reference-mappings/{mid}", headers=auth).status_code == 204


def test_reference_mapping_invalid_kind(client, auth):
    resp = client.post(
        "/api/admin/reference-mappings",
        headers=auth,
        json={"kind": "bogus", "b24_value": "1", "ms_type": "x", "ms_id": "y"},
    )
    assert resp.status_code == 422


def test_reference_mapping_used_by_workflow(monkeypatch):
    # seed a supplier (counterparty) mapping for Bitrix24 company 77
    with session_scope() as s:
        ReferenceMappingService.upsert(
            s, "counterparty", "77", "counterparty", "ms-cp-77", "Поставщик 77"
        )

    monkeypatch.setenv("SUPPLIER_DOCS_ENTITY_TYPE_ID", "1030")
    from src.config import reload_settings

    reload_settings()

    op_id = OperationService().create_and_enqueue(
        OperationDraft(
            type="create_supplier_docs",
            source="bitrix24",
            workflow_key="create_supplier_docs",
            idempotency_key="sd-map-1",
            payload={"entity_type_id": "1030", "item_id": "42", "stage_id": "S1"},
        )
    )
    with session_scope() as s:
        from src.db.models import Operation

        op = s.get(Operation, op_id)
        cp = op.result["after"]["mappings"]["counterparty"]
    assert cp["source"] == "mapping"
    assert cp["id"] == "ms-cp-77"
