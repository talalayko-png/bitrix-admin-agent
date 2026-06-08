"""Example workflow: Bitrix24 deal -> MoySklad customer order."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.entities import OperationDraft, WebhookEnvelope
from src.services.idempotency import idempotency_key
from src.workflows.base import PlanResult, Workflow

if TYPE_CHECKING:
    from src.services.context import ExecutionContext


class DealToOrderWorkflow(Workflow):
    key = "deal_to_order"
    type = "deal_to_order"
    name = "Сделка Bitrix24 → Заказ МойСклад"
    trigger_source = "bitrix24"

    MATCH_EVENTS = {
        "ONCRMDEALADD",
        "ONCRMDEALUPDATE",
        "deal.add",
        "deal.update",
    }

    def matches(self, envelope: WebhookEnvelope) -> bool:
        if envelope.source != "bitrix24":
            return False
        if envelope.event_type not in self.MATCH_EVENTS:
            return False
        return bool(self._deal_id(envelope.payload))

    def build_draft(self, envelope: WebhookEnvelope) -> OperationDraft | None:
        deal_id = self._deal_id(envelope.payload)
        if not deal_id:
            return None
        stage = (
            envelope.payload.get("STAGE_ID")
            or envelope.payload.get("stage")
            or envelope.payload.get("stage_id")
            or "any"
        )
        return OperationDraft(
            type=self.type,
            source="bitrix24",
            workflow_key=self.key,
            idempotency_key=idempotency_key("deal_to_order", deal_id, stage),
            payload={"deal_id": str(deal_id), "stage": str(stage)},
        )

    def plan(self, ctx: ExecutionContext, payload: dict[str, Any]) -> PlanResult:
        deal_id = str(payload.get("deal_id"))
        b24 = ctx.connectors.bitrix24
        ms = ctx.connectors.moysklad

        deal = b24.get_deal(deal_id)
        products = b24.get_deal_products(deal_id)
        order_payload = self._map_order(deal, products)

        existing = ms.find_order_by_external(deal_id)
        action = "update" if existing else "create"
        summary = (
            f"{action} заказ на сумму {order_payload['sum']} "
            f"{order_payload['currency']} ({len(order_payload['positions'])} позиц.)"
        )
        return PlanResult(
            action=action,
            entity_ref=f"moysklad:customerorder:ext={deal_id}",
            before=existing,
            after=order_payload,
            summary=summary,
        )

    def apply(self, ctx: ExecutionContext, plan: PlanResult) -> dict[str, Any]:
        ms = ctx.connectors.moysklad
        after = plan.after or {}
        if plan.action == "create":
            result = ms.create_order(after)
        else:
            order_id = (plan.before or {}).get("id")
            result = ms.update_order(order_id, after)
        ctx.link(
            b24_type="deal",
            b24_id=str(after.get("externalCode")),
            ms_type="customerorder",
            ms_id=str(result.get("id")),
            meta={"sum": after.get("sum")},
        )
        return result

    # ----- helpers -----
    @staticmethod
    def _deal_id(payload: dict[str, Any]) -> str | None:
        for candidate in (
            payload.get("deal_id"),
            payload.get("ID"),
            payload.get("id"),
            (payload.get("FIELDS") or {}).get("ID"),
            (payload.get("data") or {}).get("FIELDS", {}).get("ID"),
        ):
            if candidate:
                return str(candidate)
        return None

    @staticmethod
    def _map_order(deal: dict[str, Any], products: list[dict[str, Any]]) -> dict[str, Any]:
        positions = [
            {
                "name": p.get("PRODUCT_NAME") or p.get("name") or "Позиция",
                "price": float(p.get("PRICE", 0) or 0),
                "quantity": float(p.get("QUANTITY", 1) or 1),
            }
            for p in products
        ]
        total = sum(pos["price"] * pos["quantity"] for pos in positions)
        if not total:
            total = float(deal.get("OPPORTUNITY", 0) or 0)
        return {
            "name": deal.get("TITLE") or f"Заказ по сделке {deal.get('ID')}",
            "externalCode": str(deal.get("ID")),
            "currency": deal.get("CURRENCY_ID", "RUB"),
            "sum": total,
            "positions": positions,
        }
