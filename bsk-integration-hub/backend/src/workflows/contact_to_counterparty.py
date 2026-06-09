"""Workflow: Bitrix24 contact -> MoySklad counterparty."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.entities import OperationDraft, WebhookEnvelope
from src.services.idempotency import idempotency_key
from src.workflows.base import PlanResult, Workflow

if TYPE_CHECKING:
    from src.services.context import ExecutionContext


class ContactToCounterpartyWorkflow(Workflow):
    key = "contact_to_counterparty"
    type = "contact_to_counterparty"
    name = "Контакт Bitrix24 → Контрагент МойСклад"
    trigger_source = "bitrix24"

    MATCH_EVENTS = {
        "ONCRMCONTACTADD",
        "ONCRMCONTACTUPDATE",
        "contact.add",
        "contact.update",
    }

    def matches(self, envelope: WebhookEnvelope) -> bool:
        if envelope.source != "bitrix24" or envelope.event_type not in self.MATCH_EVENTS:
            return False
        return bool(self._contact_id(envelope.payload))

    def build_draft(self, envelope: WebhookEnvelope) -> OperationDraft | None:
        contact_id = self._contact_id(envelope.payload)
        if not contact_id:
            return None
        return OperationDraft(
            type=self.type,
            source="bitrix24",
            workflow_key=self.key,
            idempotency_key=idempotency_key("contact_to_counterparty", contact_id),
            payload={"contact_id": str(contact_id)},
        )

    def plan(self, ctx: ExecutionContext, payload: dict[str, Any]) -> PlanResult:
        contact_id = str(payload.get("contact_id"))
        contact = ctx.connectors.bitrix24.get_contact(contact_id)
        cp_payload = self._map_counterparty(contact)
        existing = ctx.connectors.moysklad.find_counterparty_by_external(contact_id)
        action = "update" if existing else "create"
        return PlanResult(
            action=action,
            entity_ref=f"moysklad:counterparty:ext={contact_id}",
            before=existing,
            after=cp_payload,
            summary=f"{action} контрагента «{cp_payload['name']}»",
        )

    def apply(self, ctx: ExecutionContext, plan: PlanResult) -> dict[str, Any]:
        ms = ctx.connectors.moysklad
        after = plan.after or {}
        if plan.action == "create":
            result = ms.create_counterparty(after)
        else:
            result = ms.update_counterparty((plan.before or {}).get("id"), after)
        ctx.link(
            b24_type="contact",
            b24_id=str(after.get("externalCode")),
            ms_type="counterparty",
            ms_id=str(result.get("id")),
        )
        return result

    @staticmethod
    def _contact_id(payload: dict[str, Any]) -> str | None:
        for candidate in (
            payload.get("contact_id"),
            payload.get("ID"),
            payload.get("id"),
            (payload.get("FIELDS") or {}).get("ID"),
        ):
            if candidate:
                return str(candidate)
        return None

    @staticmethod
    def _map_counterparty(contact: dict[str, Any]) -> dict[str, Any]:
        name = " ".join(
            x for x in [contact.get("NAME"), contact.get("LAST_NAME")] if x
        ).strip()
        if not name:
            name = contact.get("COMPANY_TITLE") or f"Контакт {contact.get('ID')}"
        return {
            "name": name,
            "externalCode": str(contact.get("ID")),
            "phone": contact.get("PHONE", ""),
            "email": contact.get("EMAIL", ""),
        }
