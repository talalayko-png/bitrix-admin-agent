"""Workflow: Bitrix24 smart-process item -> MoySklad supplier documents.

Dry-run first. ``plan`` produces a rich, side-effect-free preview:
  * what data arrived from Bitrix24 (item, product rows, fields);
  * which required fields were validated;
  * which Bitrix24 <-> MoySklad mappings were resolved;
  * which MoySklad documents would be created and with what payloads;
  * which fields would be written back to Bitrix24.

No writes happen in dry-run. The ``apply`` (write) path creates a purchase order
and a supplier invoice and writes ids back to Bitrix24 — all via ``guard_write``,
so it is blocked unless write mode is enabled. Goods receipt (приёмка) is NOT
created here (future, explicitly-confirmed workflow only).
"""

from __future__ import annotations

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

        item = b24.get_item(etid, item_id)
        rows = b24.get_item_products(etid, item_id)
        fields_desc = b24.get_item_fields(etid)

        # 1) received
        received = {
            "item": item,
            "product_rows": rows,
            "available_fields": sorted(fields_desc.keys()),
        }

        # 2) validation of required fields
        supplier_b24 = str(item.get("companyId") or item.get("COMPANY_ID") or "")
        amount = self._amount(item, rows)
        validation = {
            "has_supplier": bool(supplier_b24),
            "has_products": bool(rows),
            "has_amount": amount > 0,
        }
        required_ok = all(validation.values())

        # 3) mappings B24 <-> MS
        org = ms.find_organization(s.moysklad_default_organization)
        store = ms.find_store(s.moysklad_default_store)
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

        # 4) idempotency: already written back to B24?
        po_field = s.bitrix24_writeback_purchaseorder_field or _PO_FIELD_DEFAULT
        inv_field = s.bitrix24_writeback_invoicein_field or _INV_FIELD_DEFAULT
        already_po = item.get(po_field) or None
        already_inv = item.get(inv_field) or None
        already_processed = bool(already_po or already_inv)

        external = f"b24-{etid}-{item_id}"

        # 5) documents that WOULD be created (preview payloads, nothing sent)
        po_payload = {
            "name": item.get("title") or f"Закупка {item_id}",
            "externalCode": external,
            "organization": meta_ref(base, "organization", org["id"]) if org else None,
            "agent": meta_ref(base, "counterparty", supplier["id"]) if supplier else None,
            "store": meta_ref(base, "store", store["id"]) if store else None,
            "positions": positions_payload(base, resolved_positions),
        }
        inv_payload = {
            "name": f"Счёт по закупке {item_id}",
            "externalCode": external + "-inv",
            "organization": meta_ref(base, "organization", org["id"]) if org else None,
            "agent": meta_ref(base, "counterparty", supplier["id"]) if supplier else None,
        }
        documents = [
            {"type": "purchaseorder", "payload": po_payload},
            {"type": "invoicein", "payload": inv_payload},
        ]

        # 6) fields that WOULD be written back to B24
        writeback = {po_field: "<ms purchaseorder id>", inv_field: "<ms invoicein id>"}

        if already_processed:
            action = "noop"
            summary = "Уже обработано: документы МС записаны в Б24 ранее"
        elif required_ok:
            action = "create"
            summary = (
                f"Создать заказ поставщику и счёт на сумму {amount} "
                f"({len(resolved_positions)}/{len(rows)} позиций сопоставлено)"
            )
        else:
            action = "blocked"
            missing = [k for k, ok in validation.items() if not ok]
            summary = f"Не хватает обязательных данных: {', '.join(missing)}"

        after = {
            "received": received,
            "validation": {**validation, "required_ok": required_ok},
            "mappings": mappings,
            "documents": documents,
            "writeback": writeback,
        }
        before = (
            {"already_processed": True, po_field: already_po, inv_field: already_inv}
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

        ms = ctx.connectors.moysklad
        b24 = ctx.connectors.bitrix24
        documents = (plan.after or {}).get("documents", [])
        po_payload = next((d["payload"] for d in documents if d["type"] == "purchaseorder"), {})
        inv_payload = next((d["payload"] for d in documents if d["type"] == "invoicein"), {})

        purchase_order = ms.create_purchaseorder(po_payload)
        invoice = ms.create_invoicein(inv_payload)

        b24.update_item(
            meta["entity_type_id"],
            meta["item_id"],
            {
                meta["po_field"]: purchase_order.get("id"),
                meta["inv_field"]: invoice.get("id"),
            },
        )
        ctx.link(
            b24_type=f"smartitem:{meta['entity_type_id']}",
            b24_id=str(meta["item_id"]),
            ms_type="purchaseorder",
            ms_id=str(purchase_order.get("id")),
            meta={"invoicein": invoice.get("id")},
        )
        return {"purchaseorder": purchase_order.get("id"), "invoicein": invoice.get("id")}

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
