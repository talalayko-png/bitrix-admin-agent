"""Workflow: Bitrix24 smart-process item -> MoySklad supplier documents.

Бизнес-сценарий «Снабжение» (СПА 1066, стадия «Счёт получен / отправлен в
оплату»): в МойСклад создаётся цепочка из трёх документов:

  1. Заказ поставщику (``purchaseorder``) — проведён, позиции «в ожидании»
     (флаг ``wait``), склад — из поля «Склад МС» материнской сделки,
     план. дата приёмки — из поля «Плановая дата готовности у поставщика»;
  2. Счёт поставщика (``invoicein``) — проведён, на основании заказа,
     план. дата оплаты — из «Дата оплаты поставщику», входящий номер и дата —
     из «№ и дата счёта поставщика»;
  3. Приёмка (``supply``) — НЕ проведена, на основании счёта, на дату
     «Плановая дата готовности у поставщика».

Dry-run first. ``plan`` produces a rich, side-effect-free preview:
  * what data arrived from Bitrix24 (item, product rows, parent deal);
  * which required fields were validated (+ warnings);
  * which Bitrix24 <-> MoySklad mappings were resolved;
  * which B24 fields feed which MS attributes (``field_sources``);
  * which MoySklad documents would be created and with what payloads;
  * which fields would be written back to Bitrix24.

No writes happen in dry-run. The ``apply`` (write) path runs via ``guard_write``
and is blocked unless write mode is explicitly enabled.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from src.config import get_settings
from src.connectors.moysklad.meta import meta_ref, positions_payload
from src.domain.entities import OperationDraft, WebhookEnvelope
from src.services.idempotency import idempotency_key
from src.services.reference_mapping import ReferenceMappingService
from src.workflows.base import PlanResult, Workflow

if TYPE_CHECKING:
    from src.services.context import ExecutionContext

_PO_FIELD_DEFAULT = "ufCrm_PO_ID"
_INV_FIELD_DEFAULT = "ufCrm_INV_ID"

_MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11,
    "декабря": 12,
}


def b24_date_to_ms(value: Any) -> str | None:
    """B24 ISO date ("2026-06-08T03:00:00+03:00") -> MoySklad "2026-06-08 00:00:00".

    Берём календарную дату как она записана в Б24 (без сдвига таймзон)."""
    text = str(value or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00:00"


def parse_invoice_ref(raw: Any) -> dict[str, Any]:
    """«№ и дата счёта поставщика» (свободный текст) -> входящий номер + дата.

    Понимает «1021 от 2 июня 2026 г.», «7191 от 04.06.2026», «77 от 04.06.26»
    и просто «1021». Если дату разобрать нельзя (например «от 04.06» без года),
    дата остаётся пустой, а сырой текст сохраняется для превью."""
    text = str(raw or "").strip()
    out: dict[str, Any] = {"raw": text, "number": None, "date": None}
    if not text:
        return out
    number, sep, rest = text.partition(" от ")
    out["number"] = (number if sep else text).strip().strip(".,;") or None
    rest = rest.strip()
    if not rest:
        return out
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", rest)
    if not m:
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2})(?!\d)", rest)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        out["date"] = f"{year:04d}-{month:02d}-{day:02d} 00:00:00"
        return out
    m = re.search(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", rest, re.IGNORECASE)
    if m and m.group(2).lower() in _MONTHS_RU:
        day, month, year = int(m.group(1)), _MONTHS_RU[m.group(2).lower()], int(m.group(3))
        out["date"] = f"{year:04d}-{month:02d}-{day:02d} 00:00:00"
    return out


class CreateSupplierDocsWorkflow(Workflow):
    key = "create_supplier_docs"
    type = "create_supplier_docs"
    name = "Смарт-процесс Bitrix24 → документы поставщику МойСклад"
    trigger_source = "bitrix24"

    MATCH_EVENTS = {
        "ONCRMDYNAMICITEMADD",
        "ONCRMDYNAMICITEMUPDATE",
        "item.add",
        "item.update",
    }

    # ----------------------------------------------------------- matching
    def matches(self, envelope: WebhookEnvelope) -> bool:
        if envelope.source != "bitrix24":
            return False
        if not self._is_item_event(envelope.event_type):
            return False
        p = envelope.payload
        if not (p.get("entity_type_id") and p.get("item_id")):
            return False
        s = get_settings()
        if s.supplier_docs_entity_type_id and str(p.get("entity_type_id")) != str(
            s.supplier_docs_entity_type_id
        ):
            return False
        if s.supplier_docs_target_stage and str(p.get("stage_id") or "") != str(
            s.supplier_docs_target_stage
        ):
            return False
        return True

    def build_draft(self, envelope: WebhookEnvelope) -> OperationDraft | None:
        p = envelope.payload
        etid = str(p.get("entity_type_id"))
        item_id = str(p.get("item_id"))
        target_stage = get_settings().supplier_docs_target_stage or "any"
        return OperationDraft(
            type=self.type,
            source="bitrix24",
            workflow_key=self.key,
            idempotency_key=idempotency_key(
                "create_supplier_docs", etid, item_id, target_stage
            ),
            payload={
                "entity_type_id": etid,
                "item_id": item_id,
                "stage_id": p.get("stage_id"),
            },
        )

    # ----------------------------------------------------------- planning
    def plan(self, ctx: ExecutionContext, payload: dict[str, Any]) -> PlanResult:
        s = ctx.settings
        b24 = ctx.connectors.bitrix24
        ms = ctx.connectors.moysklad
        etid = str(payload.get("entity_type_id"))
        item_id = str(payload.get("item_id"))
        base = s.moysklad_base_url
        warnings: list[str] = []

        item = b24.get_item(etid, item_id)
        try:
            rows = b24.get_item_products(etid, item_id)
        except Exception as exc:  # права вебхука могут не покрывать productrow
            rows = []
            warnings.append(f"товарные позиции Б24 не прочитаны: {exc}")
        fields_desc = b24.get_item_fields(etid)

        def field_title(code: str) -> str:
            meta = fields_desc.get(code)
            return meta.get("title", code) if isinstance(meta, dict) else code

        # --- материнская сделка (источник поля «Склад МС») ---
        parent_deal_id = str(item.get("parentId2") or "") or None
        parent_deal: dict[str, Any] = {}
        if parent_deal_id:
            try:
                parent_deal = b24.get_deal(parent_deal_id) or {}
            except Exception as exc:
                warnings.append(f"материнская сделка {parent_deal_id} не прочитана: {exc}")

        # 1) received
        received = {
            "item": item,
            "product_rows": rows,
            "available_fields": sorted(fields_desc.keys()),
            "parent_deal_id": parent_deal_id,
        }

        # --- значения исходных полей Б24 (коды настраиваются через .env) ---
        ready_raw = item.get(s.supplier_docs_field_ready_date)
        payment_raw = item.get(s.supplier_docs_field_payment_date)
        invoice_raw = item.get(s.supplier_docs_field_invoice_ref)
        ready_date = b24_date_to_ms(ready_raw)
        payment_date = b24_date_to_ms(payment_raw)
        invoice_ref = parse_invoice_ref(invoice_raw)
        if invoice_ref["raw"] and not invoice_ref["date"]:
            warnings.append(
                f"дата из «{field_title(s.supplier_docs_field_invoice_ref)}» не разобрана: "
                f"«{invoice_ref['raw']}»"
            )

        store_field = s.supplier_docs_deal_store_field
        store_raw = parent_deal.get(store_field) if store_field else None
        if not store_field:
            warnings.append(
                "код поля «Склад МС» сделки не настроен (SUPPLIER_DOCS_DEAL_STORE_FIELD) — "
                "используется склад по умолчанию"
            )
        elif parent_deal and not store_raw:
            warnings.append(
                f"поле «Склад МС» ({store_field}) в сделке пусто — "
                "используется склад по умолчанию"
            )

        # 2) validation of required fields
        supplier_b24 = str(item.get("companyId") or item.get("COMPANY_ID") or "")
        amount = self._amount(item, rows)

        # 3) mappings B24 <-> MS
        org = ms.find_organization(s.moysklad_default_organization)
        store = (
            self._resolve(ctx, "store", str(store_raw), ms.find_store)
            if store_raw
            else None
        )
        if store_raw and store is None:
            warnings.append(f"склад «{store_raw}» не найден в МС — взят склад по умолчанию")
        if store is None:
            default_store = ms.find_store(s.moysklad_default_store)
            store = (
                {**default_store, "source": "default"} if default_store else None
            )
        supplier = self._resolve(
            ctx, "counterparty", supplier_b24, ms.find_counterparty_by_external
        )

        product_mappings: list[dict[str, Any]] = []
        resolved_positions: list[dict[str, Any]] = []
        for r in rows:
            pid = str(r.get("productId") or r.get("PRODUCT_ID") or "")
            prod = self._resolve(ctx, "product", pid, ms.find_product_by_external)
            product_mappings.append({"b24_product_id": pid, "ms": prod, "resolved": bool(prod)})
            if prod:
                resolved_positions.append(
                    {
                        "ms_product_id": prod["id"],
                        "quantity": float(r.get("quantity", 1) or 1),
                        "price": float(r.get("price", 0) or 0) * 100,  # kopecks
                    }
                )
        mappings = {
            "organization": org,
            "store": store,
            "counterparty": supplier,
            "products": product_mappings,
        }

        validation = {
            "has_supplier": bool(supplier_b24),
            "has_products": bool(rows),
            "has_amount": amount > 0,
            "has_store": store is not None,
        }
        required_ok = all(validation.values())

        # какие поля Б24 куда идут в МС (для проверки маппинга владельцем)
        field_sources = [
            {
                "b24_field": s.supplier_docs_field_ready_date,
                "b24_title": field_title(s.supplier_docs_field_ready_date),
                "b24_value": ready_raw,
                "ms_target": "purchaseorder.deliveryPlannedMoment + supply.moment",
                "ms_value": ready_date,
            },
            {
                "b24_field": s.supplier_docs_field_payment_date,
                "b24_title": field_title(s.supplier_docs_field_payment_date),
                "b24_value": payment_raw,
                "ms_target": "invoicein.paymentPlannedMoment",
                "ms_value": payment_date,
            },
            {
                "b24_field": s.supplier_docs_field_invoice_ref,
                "b24_title": field_title(s.supplier_docs_field_invoice_ref),
                "b24_value": invoice_raw,
                "ms_target": "invoicein.incomingNumber + invoicein.incomingDate",
                "ms_value": {"number": invoice_ref["number"], "date": invoice_ref["date"]},
            },
            {
                "b24_field": f"deal.{store_field or '<не настроено>'}",
                "b24_title": "Склад МС (материнская сделка)",
                "b24_value": store_raw,
                "ms_target": "purchaseorder.store + supply.store",
                "ms_value": store.get("name") if store else None,
            },
        ]

        # 4) idempotency: already written back to B24?
        po_field = s.bitrix24_writeback_purchaseorder_field or _PO_FIELD_DEFAULT
        inv_field = s.bitrix24_writeback_invoicein_field or _INV_FIELD_DEFAULT
        supply_field = s.bitrix24_writeback_supply_field or ""
        already_po = item.get(po_field) or None
        already_inv = item.get(inv_field) or None
        already_supply = item.get(supply_field) if supply_field else None
        already_processed = bool(already_po or already_inv or already_supply)

        external = f"b24-{etid}-{item_id}"
        org_ref = meta_ref(base, "organization", org["id"]) if org else None
        agent_ref = meta_ref(base, "counterparty", supplier["id"]) if supplier else None
        store_ref = meta_ref(base, "store", store["id"]) if store else None

        # 5) documents that WOULD be created (preview payloads, nothing sent).
        # Позиции заказа — с флагом wait=True («ожидание» в МС living on positions).
        po_positions = [
            {**p, "wait": True}
            for p in positions_payload(base, resolved_positions)
        ]
        po_payload = {
            "name": item.get("title") or f"Закупка {item_id}",
            "externalCode": external,
            "applicable": True,  # «проведено»
            "deliveryPlannedMoment": ready_date,
            "organization": org_ref,
            "agent": agent_ref,
            "store": store_ref,
            "positions": po_positions,
        }
        inv_payload = {
            "name": f"Счёт по закупке {item_id}",
            "externalCode": external + "-inv",
            "applicable": True,  # «проведено»
            "paymentPlannedMoment": payment_date,
            "incomingNumber": invoice_ref["number"],
            "incomingDate": invoice_ref["date"],
            "organization": org_ref,
            "agent": agent_ref,
            "positions": positions_payload(base, resolved_positions),
        }
        supply_payload = {
            "name": f"Приёмка по закупке {item_id}",
            "externalCode": external + "-sup",
            "applicable": False,  # «проведено» снято
            "moment": ready_date,
            "organization": org_ref,
            "agent": agent_ref,
            "store": store_ref,
            "positions": positions_payload(base, resolved_positions),
        }
        documents = [
            {
                "type": "purchaseorder",
                "payload": po_payload,
                "links": {},
            },
            {
                "type": "invoicein",
                "payload": inv_payload,
                "links": {"purchaseOrder": "<ссылка на созданный заказ поставщику>"},
            },
            {
                "type": "supply",
                "payload": supply_payload,
                "links": {
                    "purchaseOrder": "<ссылка на созданный заказ поставщику>",
                    "invoicesIn": "<ссылка на созданный счёт поставщика>",
                },
            },
        ]

        # 6) fields that WOULD be written back to B24
        writeback = {po_field: "<ms purchaseorder id>", inv_field: "<ms invoicein id>"}
        if supply_field:
            writeback[supply_field] = "<ссылка на приёмку в МС>"

        if already_processed:
            action = "noop"
            summary = "Уже обработано: документы МС записаны в Б24 ранее"
        elif required_ok:
            action = "create"
            summary = (
                f"Создать заказ поставщику + счёт + приёмку (не проведена) "
                f"на сумму {amount} "
                f"({len(resolved_positions)}/{len(rows)} позиций сопоставлено)"
            )
        else:
            action = "blocked"
            missing = [k for k, ok in validation.items() if not ok]
            summary = f"Не хватает обязательных данных: {', '.join(missing)}"

        after = {
            "received": received,
            "validation": {**validation, "required_ok": required_ok},
            "warnings": warnings,
            "field_sources": field_sources,
            "mappings": mappings,
            "documents": documents,
            "writeback": writeback,
        }
        before = (
            {
                "already_processed": True,
                po_field: already_po,
                inv_field: already_inv,
                **({supply_field: already_supply} if supply_field else {}),
            }
            if already_processed
            else None
        )
        return PlanResult(
            action=action,
            entity_ref=f"moysklad:purchaseorder:ext={external}",
            before=before,
            after=after,
            summary=summary,
            meta={
                "entity_type_id": etid,
                "item_id": item_id,
                "external": external,
                "po_field": po_field,
                "inv_field": inv_field,
                "supply_field": supply_field,
                "required_ok": required_ok,
                "action": action,
            },
        )

    # ----------------------------------------------------------- applying
    def apply(self, ctx: ExecutionContext, plan: PlanResult) -> dict[str, Any]:
        meta = plan.meta or {}
        if meta.get("action") == "noop":
            ctx.log("info", "Skip: supplier docs already created (idempotent)")
            return {"noop": True}
        if meta.get("action") == "blocked" or not meta.get("required_ok"):
            raise RuntimeError("create_supplier_docs: required fields missing")

        s = ctx.settings
        base = s.moysklad_base_url
        ms = ctx.connectors.moysklad
        b24 = ctx.connectors.bitrix24
        documents = (plan.after or {}).get("documents", [])

        def doc_payload(doc_type: str) -> dict[str, Any]:
            return next((d["payload"] for d in documents if d["type"] == doc_type), {})

        purchase_order = ms.create_purchaseorder(doc_payload("purchaseorder"))
        po_ref = meta_ref(base, "purchaseorder", purchase_order["id"])

        invoice = ms.create_invoicein({**doc_payload("invoicein"), "purchaseOrder": po_ref})
        inv_ref = meta_ref(base, "invoicein", invoice["id"])

        supply = ms.create_supply(
            {**doc_payload("supply"), "purchaseOrder": po_ref, "invoicesIn": [inv_ref]}
        )

        writeback_fields = {
            meta["po_field"]: purchase_order.get("id"),
            meta["inv_field"]: invoice.get("id"),
        }
        if meta.get("supply_field"):
            writeback_fields[meta["supply_field"]] = (
                f"https://online.moysklad.ru/app/#supply/edit?id={supply.get('id')}"
            )
        b24.update_item(meta["entity_type_id"], meta["item_id"], writeback_fields)
        ctx.link(
            b24_type=f"smartitem:{meta['entity_type_id']}",
            b24_id=str(meta["item_id"]),
            ms_type="purchaseorder",
            ms_id=str(purchase_order.get("id")),
            meta={"invoicein": invoice.get("id"), "supply": supply.get("id")},
        )
        return {
            "purchaseorder": purchase_order.get("id"),
            "invoicein": invoice.get("id"),
            "supply": supply.get("id"),
        }

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _is_item_event(event_type: str) -> bool:
        return (
            event_type in CreateSupplierDocsWorkflow.MATCH_EVENTS
            or event_type.startswith("ONCRMDYNAMICITEM")
        )

    @staticmethod
    def _amount(item: dict[str, Any], rows: list[dict[str, Any]]) -> float:
        total = sum(
            float(r.get("price", 0) or 0) * float(r.get("quantity", 1) or 1) for r in rows
        )
        if not total:
            total = float(item.get("opportunity", 0) or 0)
        return total

    @staticmethod
    def _resolve(
        ctx: ExecutionContext, kind: str, b24_value: str, ms_finder
    ) -> dict[str, Any] | None:
        if not b24_value:
            return None
        row = ReferenceMappingService.resolve(ctx.session, kind, b24_value)
        if row is not None:
            return {"id": row.ms_id, "name": row.ms_name, "source": "mapping"}
        found = ms_finder(b24_value)
        if found:
            return {"id": found.get("id"), "name": found.get("name"), "source": "lookup"}
        return None
