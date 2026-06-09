"""Real Bitrix24 client (guarded).

Reads are gated by ``guard_read`` (allowed in 'real reads + dry-run' mode);
writes by ``guard_write`` (require dry-run off). A custom ``httpx`` transport can
be injected for offline tests (``httpx.MockTransport``).
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config import Settings
from src.connectors.base import CallRecorder, guard_read, guard_write


class Bitrix24Client(CallRecorder):
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._base = settings.bitrix24_outbound_webhook_url.rstrip("/")
        self._transport = transport

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}/{method}.json"
        with httpx.Client(timeout=30, transport=self._transport) as client:
            resp = client.post(url, json=params)
            resp.raise_for_status()
            return resp.json()

    # ---- reads ----
    def get_deal(self, deal_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.deal.get")
        self._record("get_deal", deal_id=deal_id)
        return self._call("crm.deal.get", {"id": deal_id}).get("result", {})

    def get_deal_products(self, deal_id: str) -> list[dict[str, Any]]:
        guard_read(self._settings, "bitrix24.crm.deal.productrows.get")
        self._record("get_deal_products", deal_id=deal_id)
        return self._call("crm.deal.productrows.get", {"id": deal_id}).get("result", [])

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.contact.get")
        self._record("get_contact", contact_id=contact_id)
        return self._call("crm.contact.get", {"id": contact_id}).get("result", {})

    def get_product(self, product_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.product.get")
        self._record("get_product", product_id=product_id)
        return self._call("crm.product.get", {"id": product_id}).get("result", {})

    # ---- writes ----
    def update_deal(self, deal_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "bitrix24.crm.deal.update")
        self._record("update_deal", deal_id=deal_id, fields=fields)
        return self._call("crm.deal.update", {"id": deal_id, "fields": fields})
