"""Inbound webhook endpoints for Bitrix24 and MoySklad.

They verify the HMAC signature, persist the event, hand it to the workflow
engine (which enqueues operations) and return ``200`` quickly.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.config import get_settings
from src.logging_conf import get_logger
from src.services.webhooks import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger("api.webhooks")
service = WebhookService()


async def _parse_body(request: Request) -> tuple[bytes, dict[str, Any]]:
    raw = await request.body()
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return raw, json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return raw, dict(form)
    # best effort: try JSON, else empty
    try:
        return raw, json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return raw, {}


def _check_signature(secret: str, raw: bytes, signature: str | None) -> bool:
    """Returns signature validity and raises 401 if a secret is configured but
    the signature is missing/invalid."""
    if not secret:
        log.warning("inbound webhook secret not configured — accepting unsigned event")
        return False
    valid = service.verify_signature(secret, raw, signature)
    if not valid:
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    return True


@router.post("/bitrix24")
async def bitrix24_webhook(request: Request) -> dict[str, Any]:
    settings = get_settings()
    raw, body = await _parse_body(request)
    signature = request.headers.get("x-signature")
    valid = _check_signature(settings.bitrix24_inbound_webhook_secret, raw, signature)

    event_type = str(body.get("event") or body.get("event_type") or "unknown")
    payload = body.get("data") or {k: v for k, v in body.items() if k != "event"} or body
    return service.handle("bitrix24", event_type, payload, valid)


@router.post("/moysklad")
async def moysklad_webhook(request: Request) -> dict[str, Any]:
    settings = get_settings()
    raw, body = await _parse_body(request)
    signature = request.headers.get("x-signature")
    valid = _check_signature(settings.moysklad_inbound_webhook_secret, raw, signature)

    events = body.get("events") or []
    event_type = "unknown"
    if events and isinstance(events, list):
        event_type = str(events[0].get("action", "unknown"))
    return service.handle("moysklad", event_type, body, valid)
