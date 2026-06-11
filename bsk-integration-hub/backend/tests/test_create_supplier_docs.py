from src.db.base import session_scope
from src.db.models import Operation
from src.domain.entities import OperationDraft
from src.services.operations import OperationService
from src.services.reference_mapping import ReferenceMappingService
from src.workflows.create_supplier_docs import b24_date_to_ms, parse_invoice_ref


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
    assert after["received"]["parent_deal_id"] == "1001"
    # required-field validation
    assert after["validation"]["required_ok"] is True
    # mappings resolved
    assert after["mappings"]["organization"]["name"] == "ООО Моя Компания"
    assert after["mappings"]["store"]["name"] == "Основной склад"
    assert after["mappings"]["products"][0]["resolved"] is True
    # documents that would be created
    assert {d["type"] for d in after["documents"]} == {
        "purchaseorder",
        "invoicein",
        "supply",
    }
    assert after["documents"][0]["payload"]["externalCode"] == "b24-1030-42"
    # fields that would be written back to B24
    assert "ufCrm_PO_ID" in after["writeback"]


def test_documents_chain_payloads():
    _, _, result = _run({"entity_type_id": "1030", "item_id": "42"}, key="sd-chain")
    docs = {d["type"]: d for d in result["after"]["documents"]}

    po = docs["purchaseorder"]["payload"]
    # заказ: проведён, позиции в «ожидании», план. дата приёмки из поля СПА
    assert po["applicable"] is True
    assert po["deliveryPlannedMoment"] == "2026-06-08 00:00:00"
    assert po["positions"] and all(p["wait"] is True for p in po["positions"])
    assert po["store"]["meta"]["type"] == "store"

    inv = docs["invoicein"]["payload"]
    # счёт: проведён, план. дата оплаты + входящий номер/дата из «№ и дата счёта»
    assert inv["applicable"] is True
    assert inv["paymentPlannedMoment"] == "2026-06-09 00:00:00"
    assert inv["incomingNumber"] == "1021"
    assert inv["incomingDate"] == "2026-06-02 00:00:00"
    assert docs["invoicein"]["links"]["purchaseOrder"]

    sup = docs["supply"]["payload"]
    # приёмка: НЕ проведена, на план. дату приёмки, на основании заказа и счёта
    assert sup["applicable"] is False
    assert sup["moment"] == "2026-06-08 00:00:00"
    assert sup["store"]["meta"]["type"] == "store"
    assert set(docs["supply"]["links"]) == {"purchaseOrder", "invoicesIn"}

    # маппинг «поле Б24 → атрибут МС» показан в превью
    sources = {f["b24_field"]: f for f in result["after"]["field_sources"]}
    assert sources["ufCrm19_1771861585"]["ms_value"] == "2026-06-08 00:00:00"
    assert sources["ufCrm19_1771512153"]["ms_value"]["number"] == "1021"


def test_store_resolved_from_parent_deal_field(monkeypatch):
    monkeypatch.setenv("SUPPLIER_DOCS_DEAL_STORE_FIELD", "UF_CRM_SKLAD_MS")
    from src.config import reload_settings

    reload_settings()
    _, _, result = _run({"entity_type_id": "1030", "item_id": "42"}, key="sd-store")
    store = result["after"]["mappings"]["store"]
    assert store["name"] == "Основной склад"
    assert store["source"] == "lookup"  # найден в МС по значению поля сделки
    sources = {f["b24_title"]: f for f in result["after"]["field_sources"]}
    assert sources["Склад МС (материнская сделка)"]["b24_value"] == "Основной склад"


def test_store_resolved_via_reference_mapping():
    # боевой сценарий: «Склад МС» сделки хранит id элемента списка Б24 (15053),
    # склад МойСклад подбирается по записи reference-mappings kind=store
    with session_scope() as s:
        ReferenceMappingService.upsert(
            s, "store", "15053", "store", "store-1", "Основной склад"
        )
    _, _, result = _run({"entity_type_id": "1030", "item_id": "42"}, key="sd-refstore")
    store = result["after"]["mappings"]["store"]
    assert store["source"] == "mapping"
    assert store["id"] == "store-1"


def test_store_falls_back_to_default_with_warning():
    # без reference-mapping id «15053» в МС не находится -> склад по умолчанию
    _, _, result = _run({"entity_type_id": "1030", "item_id": "42"}, key="sd-defstore")
    assert result["after"]["mappings"]["store"]["source"] == "default"
    assert any("не найден" in w for w in result["after"]["warnings"])


def test_dry_run_performs_no_writes():
    _, status, result = _run({"entity_type_id": "1030", "item_id": "42"}, key="sd-2")
    assert result["dry_run"] is True
    # apply() never ran -> no created document ids in the result
    assert "purchaseorder" not in result
    assert "invoicein" not in result
    assert "supply" not in result


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


# --------------------------------------------------------------- helpers
def test_b24_date_to_ms():
    assert b24_date_to_ms("2026-06-08T03:00:00+03:00") == "2026-06-08 00:00:00"
    assert b24_date_to_ms("2026-06-08") == "2026-06-08 00:00:00"
    assert b24_date_to_ms("") is None
    assert b24_date_to_ms(None) is None
    assert b24_date_to_ms("08.06.2026") is None  # неожиданный формат -> None


def test_parse_invoice_ref_formats():
    ref = parse_invoice_ref("1021 от 2 июня 2026 г.")
    assert ref["number"] == "1021"
    assert ref["date"] == "2026-06-02 00:00:00"

    ref = parse_invoice_ref("7191 от 04.06.2026")
    assert ref["number"] == "7191"
    assert ref["date"] == "2026-06-04 00:00:00"

    ref = parse_invoice_ref("77 от 04.06.26")
    assert ref["number"] == "77"
    assert ref["date"] == "2026-06-04 00:00:00"

    # дата без года не угадывается — остаётся только номер и сырой текст
    ref = parse_invoice_ref("7191 от 04.06")
    assert ref["number"] == "7191"
    assert ref["date"] is None
    assert ref["raw"] == "7191 от 04.06"

    ref = parse_invoice_ref("АБ-15")
    assert ref["number"] == "АБ-15"
    assert ref["date"] is None

    assert parse_invoice_ref("")["number"] is None
    assert parse_invoice_ref(None)["raw"] == ""
