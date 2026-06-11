"""In-memory mock MoySklad client. No network. Deterministic sample data so the
dry-run preview can resolve organization / store / counterparty / products."""

from __future__ import annotations

from typing import Any

from src.connectors.base import CallRecorder
from src.utils.ids import new_id


class MockMoySkladClient(CallRecorder):
    def __init__(self, orders: dict[str, dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._orders_by_external: dict[str, dict[str, Any]] = orders or {}
        self._counterparties_by_external: dict[str, dict[str, Any]] = {}
        self._products_by_external: dict[str, dict[str, Any]] = {
            "200": {"id": "ms-prod-200", "name": "Станок ЧПУ", "externalCode": "200"},
        }
        self._organizations: list[dict[str, Any]] = [
            {"id": "org-1", "name": "ООО Моя Компания"},
        ]
        self._stores: list[dict[str, Any]] = [
            {"id": "store-1", "name": "Основной склад"},
        ]

    @staticmethod
    def _store(bucket: dict[str, dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
        record = {"id": new_id(), **payload}
        external = str(payload.get("externalCode", ""))
        if external:
            bucket[external] = record
        return record

    # ---- references ----
    def list_organizations(self) -> list[dict[str, Any]]:
        self._record("list_organizations")
        return [dict(o) for o in self._organizations]

    def find_organization(self, name: str) -> dict[str, Any] | None:
        self._record("find_organization", name=name)
        for org in self._organizations:
            if not name or org["name"].lower() == name.lower():
                return dict(org)
        return None

    def list_stores(self) -> list[dict[str, Any]]:
        self._record("list_stores")
        return [dict(s) for s in self._stores]

    def find_store(self, name: str) -> dict[str, Any] | None:
        self._record("find_store", name=name)
        for store in self._stores:
            if not name or store["name"].lower() == name.lower():
                return dict(store)
        return None

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

    # ---- supplier documents ----
    def create_purchaseorder(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_purchaseorder", payload=payload)
        return {"id": new_id(), **payload}

    def create_invoicein(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_invoicein", payload=payload)
        return {"id": new_id(), **payload}

    def create_supply(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_supply", payload=payload)
        return {"id": new_id(), **payload}

    # ---- payments ----
    def create_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("create_payment", payload=payload)
        return {"id": new_id(), **payload}
