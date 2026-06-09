"""Inbound webhook endpoints for Bitrix24 and MoySklad.

They verify authenticity (Bitrix24: application_token or HMAC; MoySklad: shared
secret), normalize the payload, hand it to the workflow engine (which enqueues
operations) and return ``200`` quickly.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.config import get_settings
from src.connectors.bitrix24.webhook import (
    normalize_event,
    parse_bracketed,
    verify_application_token,
)
from src.logging_conf import get_logger
from src.services.webhooks import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger("api.webhooks")
service = WebhookService()


@router.post("/bitrix24")
async def bitrix24_webhook(request: Request) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.bitrix24_inbound_webhook_secret
    raw = await request.body()
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            parsed = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    else:
        form = await request.form()
        parsed = parse_bracketed(list(form.multi_items()))

    norm = normalize_event(parsed)
    valid = _verify_bitrix24(
        secret, raw, request.headers.get("x-signature"), norm["application_token"]
    )
    return service.handle("bitrix24", norm["event"], norm["payload"], valid)


def _verify_bitrix24(
    secret: str, raw: bytes, signature: str | None, application_token: str | None
) -> bool:
    """Accept either a valid application_token (Bitrix24's scheme) or a valid HMAC
    signature. If a secret is configured and neither matches, reject (401)."""
    if not secret:
        log.warning("Bitrix24 inbound secret not configured — accepting unsigned event")
        return False
    if application_token and verify_application_token(secret, application_token):
        return True
    if signature and service.verify_signature(secret, raw, signature):
        return True
    raise HTTPException(status_code=401, detail="invalid Bitrix24 webhook token/signature")


@router.post("/moysklad")
async def moysklad_webhook(request: Request) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.moysklad_inbound_webhook_secret
    raw = await request.body()
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    valid = _verify_moysklad(
        secret, raw, request.headers.get("x-signature"), request.query_params.get("secret")
    )

    events = body.get("events") or []
    event_type = "unknown"
    if events and isinstance(events, list):
        event_type = str(events[0].get("action", "unknown"))
    return service.handle("moysklad", event_type, body, valid)


def _verify_moysklad(
    secret: str, raw: bytes, signature: str | None, query_secret: str | None
) -> bool:
    """MoySklad does not HMAC-sign by default; accept a shared secret passed as a
    URL query param (?secret=...) or, if configured, an HMAC signature."""
    if not secret:
        log.warning("MoySklad inbound secret not configured — accepting unsigned event")
        return False
    import hmac

    if query_secret and hmac.compare_digest(secret, query_secret):
        return True
    if signature and service.verify_signature(secret, raw, signature):
        return True
    raise HTTPException(status_code=401, detail="invalid MoySklad webhook secret")
