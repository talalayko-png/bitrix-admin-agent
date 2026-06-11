"""In-memory mock Bitrix24 client. No network. Returns deterministic sample data."""

from __future__ import annotations

from typing import Any

from src.connectors.base import CallRecorder


class MockBitrix24Client(CallRecorder):
    """Mimics the slice of the Bitrix24 REST API the workflows need."""

    def __init__(self, deals: dict[str, dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._deals: dict[str, dict[str, Any]] = deals or {
            "1001": {
                "ID": "1001",
                "TITLE": "Сделка #1001 — поставка оборудования",
                "STAGE_ID": "WON",
                "OPPORTUNITY": "150000",
                "CURRENCY_ID": "RUB",
                "CONTACT_ID": "55",
                "ASSIGNED_BY_ID": "7",
                "UF_CRM_SKLAD_MS": "Основной склад",
                "UF_CRM_DELIVERY": "19335",
            }
        }
        self._deal_fields: dict[str, Any] = {
            "TITLE": {"title": "Название", "type": "string"},
            "UF_CRM_SKLAD_MS": {"title": "Склад МС", "type": "string"},
            "UF_CRM_DELIVERY": {
                "title": "Как доставляем",
                "type": "enumeration",
                "items": [{"ID": "19335", "VALUE": "ТК"}],
            },
        }
        self._deal_products: dict[str, list[dict[str, Any]]] = {
            "1001": [
                {"PRODUCT_NAME": "Станок ЧПУ", "PRICE": "120000", "QUANTITY": "1"},
                {"PRODUCT_NAME": "Доставка", "PRICE": "30000", "QUANTITY": "1"},
            ]
        }
        self._contacts: dict[str, dict[str, Any]] = {
            "55": {
                "ID": "55",
                "NAME": "Иван",
                "LAST_NAME": "Петров",
                "COMPANY_TITLE": "ООО Ромашка",
                "PHONE": "+7 900 000-00-00",
                "EMAIL": "ivan@example.com",
            }
        }
        self._products: dict[str, dict[str, Any]] = {
            "200": {
                "ID": "200",
                "NAME": "Станок ЧПУ",
                "PRICE": "120000",
                "CURRENCY_ID": "RUB",
                "MEASURE": "шт",
            }
        }
        # smart-process (СПА) items, keyed by item id; UF-коды полей — как на
        # боевом портале (СПА «Снабжение», см. дефолты supplier_docs_field_* в config)
        self._items: dict[str, dict[str, Any]] = {
            "42": {
                "id": "42",
                "title": "Закупка #42",
                "entityTypeId": "1030",
                "stageId": "DT1030_10:NEW",
                "companyId": "77",
                "assignedById": "7",
                "opportunity": "50000",
                "currencyId": "RUB",
                "parentId2": "1001",
                "ufCrm19_1771861585": "2026-06-08T03:00:00+03:00",
                "ufCrm19_1771861774": "2026-06-09T03:00:00+03:00",
                "ufCrm19_1771512153": "1021 от 2 июня 2026 г.",
                "ufCrm_PO_ID": "",
                "ufCrm_INV_ID": "",
            },
            # already processed (idempotency): MS purchase order id already written back
            "43": {
                "id": "43",
                "title": "Закупка #43 (обработана)",
                "entityTypeId": "1030",
                "stageId": "DT1030_10:NEW",
                "companyId": "77",
                "opportunity": "1000",
                "currencyId": "RUB",
                "ufCrm_PO_ID": "ms-po-existing",
                "ufCrm_INV_ID": "ms-inv-existing",
            },
        }
        self._item_products: dict[str, list[dict[str, Any]]] = {
            "42": [
                {
                    "productId": "200",
                    "productName": "Станок ЧПУ",
                    "price": "50000",
                    "quantity": "1",
                },
            ],
            "43": [
                {
                    "productId": "200",
                    "productName": "Станок ЧПУ",
                    "price": "1000",
                    "quantity": "1",
                },
            ],
        }
        self._item_fields: dict[str, dict[str, Any]] = {
            "ufCrm_PO_ID": {"title": "MS purchase order id", "type": "string"},
            "ufCrm_INV_ID": {"title": "MS invoice id", "type": "string"},
            "ufCrm19_1771861585": {
                "title": "Плановая дата готовности у поставщика",
                "type": "date",
            },
            "ufCrm19_1771861774": {"title": "Дата оплаты поставщику", "type": "date"},
            "ufCrm19_1771512153": {
                "title": "№ и дата счёта поставщика",
                "type": "string",
            },
        }
        self._companies: dict[str, dict[str, Any]] = {
            "77": {"ID": "77", "TITLE": "ООО Поставщик-77"},
        }

    def get_deal(self, deal_id: str) -> dict[str, Any]:
        self._record("get_deal", deal_id=deal_id)
        return dict(
            self._deals.get(
                str(deal_id),
                {
                    "ID": str(deal_id),
                    "TITLE": f"Сделка #{deal_id}",
                    "STAGE_ID": "NEW",
                    "OPPORTUNITY": "0",
                    "CURRENCY_ID": "RUB",
                },
            )
        )

    def get_deal_products(self, deal_id: str) -> list[dict[str, Any]]:
        self._record("get_deal_products", deal_id=deal_id)
        return [dict(p) for p in self._deal_products.get(str(deal_id), [])]

    def get_deal_fields(self) -> dict[str, Any]:
        self._record("get_deal_fields")
        return dict(self._deal_fields)

    def get_company(self, company_id: str) -> dict[str, Any]:
        self._record("get_company", company_id=company_id)
        return dict(
            self._companies.get(
                str(company_id),
                {"ID": str(company_id), "TITLE": f"Компания {company_id}"},
            )
        )

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        self._record("get_contact", contact_id=contact_id)
        return dict(
            self._contacts.get(
                str(contact_id),
                {"ID": str(contact_id), "NAME": f"Контакт {contact_id}", "LAST_NAME": ""},
            )
        )

    def get_product(self, product_id: str) -> dict[str, Any]:
        self._record("get_product", product_id=product_id)
        return dict(
            self._products.get(
                str(product_id),
                {
                    "ID": str(product_id),
                    "NAME": f"Товар {product_id}",
                    "PRICE": "0",
                    "CURRENCY_ID": "RUB",
                },
            )
        )

    def update_deal(self, deal_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        # Write path — only reached in real mode (mock just records).
        self._record("update_deal", deal_id=deal_id, fields=fields)
        return {"result": True, "deal_id": str(deal_id)}

    # ---- smart process (СПА) ----
    def get_item(self, entity_type_id: str, item_id: str) -> dict[str, Any]:
        self._record("get_item", entity_type_id=entity_type_id, item_id=item_id)
        item = self._items.get(str(item_id))
        if item:
            return dict(item)
        return {
            "id": str(item_id),
            "title": f"Элемент {item_id}",
            "entityTypeId": str(entity_type_id),
            "stageId": "",
            "companyId": "",
        }

    def get_item_products(self, entity_type_id: str, item_id: str) -> list[dict[str, Any]]:
        self._record("get_item_products", entity_type_id=entity_type_id, item_id=item_id)
        return [dict(p) for p in self._item_products.get(str(item_id), [])]

    def get_item_fields(self, entity_type_id: str) -> dict[str, Any]:
        self._record("get_item_fields", entity_type_id=entity_type_id)
        return dict(self._item_fields)

    def update_item(
        self, entity_type_id: str, item_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        # Write path — only reached in real (write) mode.
        self._record("update_item", entity_type_id=entity_type_id, item_id=item_id, fields=fields)
        return {"item": {"id": str(item_id), **fields}}
