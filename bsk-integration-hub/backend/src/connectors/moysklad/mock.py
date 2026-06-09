"""In-memory mock MoySklad client. No network."""

from __future__ import annotations

from typing import Any

from src.connectors.base import CallRecorder
from src.utils.ids import new_id


class MockMoySkladClient(CallRecorder):
    def __init__(self, orders: dict[str, dict[str, Any]] | None = None) -> None:
        super().__init__()
        # keyed by external (Bitrix24 deal) id
        self._orders_by_external: dict[str, dict[str, Any]] = orders or {}

    def find_order_by_external(self, external_id: str) -> dict[str, Any] | None:
        self._record("find_order_by_external", external_id=external_id)
        order = self._orders_by_external.get(str(external_id))
        return dict(order) if order else None

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Write path — only reached in real mode (mock just records + stores).
        self._record("create_order", payload=payload)
        order_id = new_id()
        record = {"id": order_id, **payload}
        external = str(payload.get("externalCode", ""))
        if external:
            self._orders_by_external[external] = record
        return record

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._record("update_order", order_id=order_id, payload=payload)
        return {"id": str(order_id), **payload}
