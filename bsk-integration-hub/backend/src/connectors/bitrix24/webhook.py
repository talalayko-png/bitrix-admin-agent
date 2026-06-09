"""Bitrix24 inbound webhook parsing, verification and normalization.

Bitrix24 outbound webhooks (robots / event handlers) POST form-encoded bodies
with bracketed keys, e.g.::

    event=ONCRMDYNAMICITEMUPDATE
    data[FIELDS][ID]=42
    data[FIELDS][ENTITY_TYPE_ID]=1030
    data[FIELDS][STAGE_ID]=DT1030_10:NEW
    auth[application_token]=<token>

Authenticity is verified by the ``application_token`` (compared to the configured
secret), not by HMAC.
"""

from __future__ import annotations

import hmac
import re
from typing import Any

_PART = re.compile(r"[^\[\]]+")


def parse_bracketed(items: list[tuple[str, str]]) -> dict[str, Any]:
    """Turn flat bracketed form items into a nested dict.

    ``data[FIELDS][ID]=42`` -> ``{"data": {"FIELDS": {"ID": "42"}}}``.
    """
    root: dict[str, Any] = {}
    for key, value in items:
        parts = _PART.findall(key)
        if not parts:
            continue
        node = root
        for part in parts[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                node[part] = nxt
            node = nxt
        node[parts[-1]] = value
    return root


def normalize_event(parsed: dict[str, Any]) -> dict[str, Any]:
    """Normalize a parsed Bitrix24 event into a canonical envelope.

    Returns ``{event, payload, application_token}`` where payload carries both the
    raw ``FIELDS`` and the normalized smart-process keys.
    """
    event = str(parsed.get("event") or parsed.get("event_type") or "unknown")
    data = parsed.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    fields = data.get("FIELDS") or {}
    if not isinstance(fields, dict):
        fields = {}
    # start from the flat data keys (so e.g. deal_id / contact_id survive)
    payload: dict[str, Any] = {k: v for k, v in data.items() if k != "FIELDS"}
    payload["FIELDS"] = fields
    payload.setdefault("ID", fields.get("ID") or data.get("ID"))
    payload["entity_type_id"] = fields.get("ENTITY_TYPE_ID") or data.get("entity_type_id")
    payload["item_id"] = fields.get("ID") or data.get("item_id") or data.get("ID")
    payload["stage_id"] = fields.get("STAGE_ID") or data.get("stage_id") or data.get("STAGE_ID")
    auth = parsed.get("auth") or {}
    return {
        "event": event,
        "payload": payload,
        "application_token": auth.get("application_token"),
    }


def verify_application_token(secret: str, token: str | None) -> bool:
    if not secret or not token:
        return False
    return hmac.compare_digest(secret, str(token))
