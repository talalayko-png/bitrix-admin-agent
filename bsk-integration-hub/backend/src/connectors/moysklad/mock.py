"""In-memory mock MoySklad client. No network."""

from __future__ import annotations

from typing import Any

from src.connectors.base import CallRecorder
from src.utils.ids import new_id


class MockMoySkladClient(CallRecorder):
    def __init__(self, orders: dict[str, dict[str, Any]] | None = None) -> None:
        super().__init__()
        # each keyed by external (Bitrix24) id
        self._orders_by_external: dict[str, dict[str, Any]] = orders or {}
        self._counterparties_by_external: dict[str, dict[str, Any]] = {}
        self._products_by_external: dict[str, dict[str, Any]] = {}

    # ---- generic helper ----
    @staticmethod
    def _store(bucket: dict[str, dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
        record = {"id": new_id(), **payload}
        external = str(payload.get("externalCode", ""))
        if external:
            bucket[external] = record
        return record

    # ---- customer orders ----
    def find_order_by_external(self, external_id: str) -> dict[str, Any] | None:
        self._record("find_order_by_external", external_id=external_id)
        order = self._orders_by_external.get(str(external_id))
        return dict(order) if order else None

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_order", payload=payload)
        return self._store(self._orders_by_external, payload)

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("update_order", order_id=order_id, payload=payload)
        return {"id": str(order_id), **payload}

    # ---- counterparties ----
    def find_counterparty_by_external(self, external_id: str) -> dict[str, Any] | None:
        self._record("find_counterparty_by_external", external_id=external_id)
        cp = self._counterparties_by_external.get(str(external_id))
        return dict(cp) if cp else None

    def create_counterparty(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_counterparty", payload=payload)
        return self._store(self._counterparties_by_external, payload)

    def update_counterparty(self, cp_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("update_counterparty", cp_id=cp_id, payload=payload)
        return {"id": str(cp_id), **payload}

    # ---- products ----
    def find_product_by_external(self, external_id: str) -> dict[str, Any] | None:
        self._record("find_product_by_external", external_id=external_id)
        product = self._products_by_external.get(str(external_id))
        return dict(product) if product else None

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_product", payload=payload)
        return self._store(self._products_by_external, payload)

    def update_product(self, product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("update_product", product_id=product_id, payload=payload)
        return {"id": str(product_id), **payload}

    # ---- payments (incoming) ----
    def create_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_payment", payload=payload)
        return {"id": new_id(), **payload}
