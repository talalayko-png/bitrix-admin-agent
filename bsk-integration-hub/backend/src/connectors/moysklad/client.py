"""Real MoySklad client (guarded). Disabled by default in the MVP.

A custom ``httpx`` transport can be injected for offline tests
(``httpx.MockTransport``); in production it is ``None``.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config import Settings
from src.connectors.base import CallRecorder, guard_egress


class MoySkladClient(CallRecorder):
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._base = settings.moysklad_base_url.rstrip("/")
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.moysklad_token}",
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=30, transport=self._transport, headers=self._headers())

    def find_order_by_external(self, external_id: str) -> dict[str, Any] | None:
        guard_egress(self._settings, "moysklad.find_order_by_external")
        self._record("find_order_by_external", external_id=external_id)
        with self._client() as client:
            resp = client.get(
                f"{self._base}/entity/customerorder",
                params={"filter": f"externalCode={external_id}"},
            )
            resp.raise_for_status()
            rows = resp.json().get("rows", [])
            return rows[0] if rows else None

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_egress(self._settings, "moysklad.create_order")
        self._record("create_order", payload=payload)
        with self._client() as client:
            resp = client.post(f"{self._base}/entity/customerorder", json=payload)
            resp.raise_for_status()
            return resp.json()

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        guard_egress(self._settings, "moysklad.update_order")
        self._record("update_order", order_id=order_id, payload=payload)
        with self._client() as client:
            resp = client.put(f"{self._base}/entity/customerorder/{order_id}", json=payload)
            resp.raise_for_status()
            return resp.json()
