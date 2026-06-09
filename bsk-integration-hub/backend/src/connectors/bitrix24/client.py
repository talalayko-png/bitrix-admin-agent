"""Real Bitrix24 client (guarded).

Implemented against the inbound webhook REST style. Every method calls
``guard_egress`` first, so nothing leaves the process unless all three safety
fuses are flipped. Disabled by default in the MVP.

A custom ``httpx`` transport can be injected (used by offline tests via
``httpx.MockTransport``); in production it is ``None`` and httpx uses the real
network transport.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config import Settings
from src.connectors.base import CallRecorder, guard_egress


class Bitrix24Client(CallRecorder):
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._base = settings.bitrix24_outbound_webhook_url.rstrip("/")
        self._transport = transport

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        guard_egress(self._settings, f"bitrix24.{method}")
        url = f"{self._base}/{method}.json"
        with httpx.Client(timeout=30, transport=self._transport) as client:
            resp = client.post(url, json=params)
            resp.raise_for_status()
            return resp.json()

    def get_deal(self, deal_id: str) -> dict[str, Any]:
        self._record("get_deal", deal_id=deal_id)
        return self._call("crm.deal.get", {"id": deal_id}).get("result", {})

    def get_deal_products(self, deal_id: str) -> list[dict[str, Any]]:
        self._record("get_deal_products", deal_id=deal_id)
        return self._call("crm.deal.productrows.get", {"id": deal_id}).get("result", [])

    def update_deal(self, deal_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self._record("update_deal", deal_id=deal_id, fields=fields)
        return self._call("crm.deal.update", {"id": deal_id, "fields": fields})
