"""Workflow: Bitrix24 catalog product -> MoySklad product (товары/остатки)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.entities import OperationDraft, WebhookEnvelope
from src.services.idempotency import idempotency_key
from src.workflows.base import PlanResult, Workflow

if TYPE_CHECKING:
    from src.services.context import ExecutionContext


class ProductSyncWorkflow(Workflow):
    key = "product_sync"
    type = "product_sync"
    name = "Товар Bitrix24 → Товар МойСклад"
    trigger_source = "bitrix24"

    MATCH_EVENTS = {
        "ONCRMPRODUCTADD",
        "ONCRMPRODUCTUPDATE",
        "product.add",
        "product.update",
        "catalog.product.update",
    }

    def matches(self, envelope: WebhookEnvelope) -> bool:
        if envelope.source != "bitrix24" or envelope.event_type not in self.MATCH_EVENTS:
            return False
        return bool(self._product_id(envelope.payload))

    def build_draft(self, envelope: WebhookEnvelope) -> OperationDraft | None:
        product_id = self._product_id(envelope.payload)
        if not product_id:
            return None
        return OperationDraft(
            type=self.type,
            source="bitrix24",
            workflow_key=self.key,
            idempotency_key=idempotency_key("product_sync", product_id),
            payload={"product_id": str(product_id)},
        )

    def plan(self, ctx: ExecutionContext, payload: dict[str, Any]) -> PlanResult:
        product_id = str(payload.get("product_id"))
        product = ctx.connectors.bitrix24.get_product(product_id)
        ms_payload = self._map_product(product)
        existing = ctx.connectors.moysklad.find_product_by_external(product_id)
        action = "update" if existing else "create"
        return PlanResult(
            action=action,
            entity_ref=f"moysklad:product:ext={product_id}",
            before=existing,
            after=ms_payload,
            summary=f"{action} товар «{ms_payload['name']}» по цене {ms_payload['price']}",
        )

    def apply(self, ctx: ExecutionContext, plan: PlanResult) -> dict[str, Any]:
        ms = ctx.connectors.moysklad
        after = plan.after or {}
        if plan.action == "create":
            result = ms.create_product(after)
        else:
            result = ms.update_product((plan.before or {}).get("id"), after)
        ctx.link(
            b24_type="product",
            b24_id=str(after.get("externalCode")),
            ms_type="product",
            ms_id=str(result.get("id")),
        )
        return result

    @staticmethod
    def _product_id(payload: dict[str, Any]) -> str | None:
        for candidate in (
            payload.get("product_id"),
            payload.get("ID"),
            payload.get("id"),
            (payload.get("FIELDS") or {}).get("ID"),
        ):
            if candidate:
                return str(candidate)
        return None

    @staticmethod
    def _map_product(product: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": product.get("NAME") or f"Товар {product.get('ID')}",
            "externalCode": str(product.get("ID")),
            "code": str(product.get("ID")),
            "price": float(product.get("PRICE", 0) or 0),
        }
