"""Workflow: Bitrix24 deal payment -> MoySklad incoming payment (оплаты).

Distinct trigger events (``payment.add`` / ``deal.payment``) so it never collides
with the deal_to_order workflow on a plain deal update.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.entities import OperationDraft, WebhookEnvelope
from src.services.idempotency import idempotency_key
from src.workflows.base import PlanResult, Workflow

if TYPE_CHECKING:
    from src.services.context import ExecutionContext


class PaymentSyncWorkflow(Workflow):
    key = "payment_sync"
    type = "payment_sync"
    name = "Оплата Bitrix24 → Входящий платёж МойСклад"
    trigger_source = "bitrix24"

    MATCH_EVENTS = {"payment.add", "deal.payment"}

    def matches(self, envelope: WebhookEnvelope) -> bool:
        if envelope.source != "bitrix24" or envelope.event_type not in self.MATCH_EVENTS:
            return False
        deal_id, amount, _ = self._extract(envelope.payload)
        return bool(deal_id and amount)

    def build_draft(self, envelope: WebhookEnvelope) -> OperationDraft | None:
        deal_id, amount, payment_id = self._extract(envelope.payload)
        if not (deal_id and amount):
            return None
        key = payment_id or f"{deal_id}:{amount}"
        return OperationDraft(
            type=self.type,
            source="bitrix24",
            workflow_key=self.key,
            idempotency_key=idempotency_key("payment_sync", key),
            payload={"deal_id": str(deal_id), "amount": float(amount), "key": str(key)},
        )

    def plan(self, ctx: ExecutionContext, payload: dict[str, Any]) -> PlanResult:
        deal_id = str(payload.get("deal_id"))
        amount = float(payload.get("amount", 0) or 0)
        key = str(payload.get("key"))
        ms_payload = {
            "externalCode": f"pay-{key}",
            "sum": amount,
            "description": f"Оплата по сделке Bitrix24 #{deal_id}",
        }
        # incoming payments are append-only: always a create
        return PlanResult(
            action="create",
            entity_ref=f"moysklad:paymentin:ext=pay-{key}",
            before=None,
            after=ms_payload,
            summary=f"create входящий платёж на {amount} по сделке #{deal_id}",
            meta={"deal_id": deal_id},
        )

    def apply(self, ctx: ExecutionContext, plan: PlanResult) -> dict[str, Any]:
        after = plan.after or {}
        result = ctx.connectors.moysklad.create_payment(after)
        ctx.link(
            b24_type="deal",
            b24_id=str((plan.meta or {}).get("deal_id", "")),
            ms_type="paymentin",
            ms_id=str(result.get("id")),
            meta={"sum": after.get("sum")},
        )
        return result

    @staticmethod
    def _extract(payload: dict[str, Any]) -> tuple[str | None, float | None, str | None]:
        fields = payload.get("FIELDS") or {}
        deal_id = payload.get("deal_id") or payload.get("DEAL_ID") or fields.get("DEAL_ID")
        amount = payload.get("amount") or payload.get("SUM") or fields.get("SUM")
        payment_id = payload.get("payment_id") or payload.get("ID") or fields.get("ID")
        try:
            amount_val = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            amount_val = None
        return (
            str(deal_id) if deal_id else None,
            amount_val,
            str(payment_id) if payment_id else None,
        )
