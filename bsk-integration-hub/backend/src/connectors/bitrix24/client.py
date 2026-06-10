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

    def get_deal_fields(self) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.deal.fields")
        self._record("get_deal_fields")
        return self._call("crm.deal.fields", {}).get("result", {})

    def get_company(self, company_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.company.get")
        self._record("get_company", company_id=company_id)
        return self._call("crm.company.get", {"id": company_id}).get("result", {})

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.contact.get")
        self._record("get_contact", contact_id=contact_id)
        return self._call("crm.contact.get", {"id": contact_id}).get("result", {})

    def get_product(self, product_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.product.get")
        self._record("get_product", product_id=product_id)
        return self._call("crm.product.get", {"id": product_id}).get("result", {})

    # ---- smart process (СПА) reads ----
    def get_item(self, entity_type_id: str, item_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.item.get")
        self._record("get_item", entity_type_id=entity_type_id, item_id=item_id)
        result = self._call(
            "crm.item.get", {"entityTypeId": entity_type_id, "id": item_id}
        ).get("result", {})
        return result.get("item", result)

    def get_item_products(self, entity_type_id: str, item_id: str) -> list[dict[str, Any]]:
        guard_read(self._settings, "bitrix24.crm.item.productrow.list")
        self._record("get_item_products", entity_type_id=entity_type_id, item_id=item_id)
        # ownerType динамического типа — "T" + entityTypeId в HEX (1066 -> "T42a"),
        # см. apidocs.bitrix24.ru: crm/data-types#object_type
        owner_type = f"T{int(entity_type_id):x}"
        result = self._call(
            "crm.item.productrow.list",
            {"filter": {"=ownerId": item_id, "=ownerType": owner_type}},
        ).get("result", {})
        return result.get("productRows", [])

    def get_item_fields(self, entity_type_id: str) -> dict[str, Any]:
        guard_read(self._settings, "bitrix24.crm.item.fields")
        self._record("get_item_fields", entity_type_id=entity_type_id)
        result = self._call("crm.item.fields", {"entityTypeId": entity_type_id}).get("result", {})
        return result.get("fields", result)

    # ---- writes ----
    def update_deal(self, deal_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "bitrix24.crm.deal.update")
        self._record("update_deal", deal_id=deal_id, fields=fields)
        return self._call("crm.deal.update", {"id": deal_id, "fields": fields})

    def update_item(
        self, entity_type_id: str, item_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        guard_write(self._settings, "bitrix24.crm.item.update")
        self._record("update_item", entity_type_id=entity_type_id, item_id=item_id, fields=fields)
        return self._call(
            "crm.item.update",
            {"entityTypeId": entity_type_id, "id": item_id, "fields": fields},
        )
