"""Real MoySklad client (guarded).

Reads are gated by ``guard_read`` (allowed in 'real reads + dry-run' mode);
writes by ``guard_write`` (require dry-run off). A custom ``httpx`` transport can
be injected for offline tests.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config import Settings
from src.connectors.base import CallRecorder, guard_read, guard_write


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

    def _find_by_external(self, entity: str, external_id: str) -> dict[str, Any] | None:
        with self._client() as client:
            resp = client.get(
                f"{self._base}/entity/{entity}",
                params={"filter": f"externalCode={external_id}"},
            )
            resp.raise_for_status()
            rows = resp.json().get("rows", [])
            return rows[0] if rows else None

    def _create(self, entity: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._client() as client:
            resp = client.post(f"{self._base}/entity/{entity}", json=payload)
            resp.raise_for_status()
            return resp.json()

    def _update(self, entity: str, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._client() as client:
            resp = client.put(f"{self._base}/entity/{entity}/{entity_id}", json=payload)
            resp.raise_for_status()
            return resp.json()

    # ---- customer orders ----
    def find_order_by_external(self, external_id: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_order_by_external")
        self._record("find_order_by_external", external_id=external_id)
        return self._find_by_external("customerorder", external_id)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_order")
        self._record("create_order", payload=payload)
        return self._create("customerorder", payload)

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.update_order")
        self._record("update_order", order_id=order_id, payload=payload)
        return self._update("customerorder", order_id, payload)

    # ---- counterparties ----
    def find_counterparty_by_external(self, external_id: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_counterparty_by_external")
        self._record("find_counterparty_by_external", external_id=external_id)
        return self._find_by_external("counterparty", external_id)

    def create_counterparty(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_counterparty")
        self._record("create_counterparty", payload=payload)
        return self._create("counterparty", payload)

    def update_counterparty(self, cp_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.update_counterparty")
        self._record("update_counterparty", cp_id=cp_id, payload=payload)
        return self._update("counterparty", cp_id, payload)

    # ---- products ----
    def find_product_by_external(self, external_id: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_product_by_external")
        self._record("find_product_by_external", external_id=external_id)
        return self._find_by_external("product", external_id)

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_product")
        self._record("create_product", payload=payload)
        return self._create("product", payload)

    def update_product(self, product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.update_product")
        self._record("update_product", product_id=product_id, payload=payload)
        return self._update("product", product_id, payload)

    # ---- payments (incoming) ----
    def create_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_payment")
        self._record("create_payment", payload=payload)
        return self._create("paymentin", payload)
