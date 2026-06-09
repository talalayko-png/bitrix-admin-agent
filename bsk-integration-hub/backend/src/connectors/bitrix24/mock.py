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
            }
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
