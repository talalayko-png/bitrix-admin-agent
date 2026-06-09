"""Inbound webhook handling: signature verification + event persistence."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from src.db.base import session_scope
from src.db.models import WebhookEvent
from src.domain.entities import WebhookEnvelope
from src.services.engine import WorkflowEngine


class WebhookService:
    @staticmethod
    def verify_signature(secret: str, raw_body: bytes, signature: str | None) -> bool:
        """HMAC-SHA256 verification. Returns False if secret or signature absent."""
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        provided = signature.split("=", 1)[1] if "=" in signature else signature
        return hmac.compare_digest(expected, provided)

    def handle(
        self,
        source: str,
        event_type: str,
        payload: dict[str, Any],
        signature_valid: bool,
    ) -> dict[str, Any]:
        # 1) persist the raw event and respond fast
        with session_scope() as session:
            event = WebhookEvent(
                source=source,
                event_type=event_type,
                payload=payload,
                signature_valid=signature_valid,
            )
            session.add(event)
            session.flush()
            event_id = event.id

        # 2) run the engine (enqueues operations)
        envelope = WebhookEnvelope(
            source=source,
            event_type=event_type,
            payload=payload,
            signature_valid=signature_valid,
        )
        operation_ids = WorkflowEngine().process(envelope)

        # 3) mark processed
        with session_scope() as session:
            event = session.get(WebhookEvent, event_id)
            if event is not None:
                event.processed = True
                if operation_ids:
                    event.operation_id = operation_ids[0]

        return {"event_id": event_id, "operation_ids": operation_ids}
