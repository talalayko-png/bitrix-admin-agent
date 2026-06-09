"""MoySklad meta/href helpers.

MoySklad links entities by a ``meta`` object that embeds an absolute ``href``.
These helpers build those references from the configured base URL so document
payloads (purchase order, invoice, etc.) point at the right organization, store,
counterparty and products.
"""

from __future__ import annotations

from typing import Any


def meta_ref(base_url: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    return {
        "meta": {
            "href": f"{base}/entity/{entity_type}/{entity_id}",
            "type": entity_type,
            "mediaType": "application/json",
        }
    }


def positions_payload(
    base_url: str, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build document positions referencing MoySklad products by id.

    Each row: {"ms_product_id": str, "quantity": float, "price": float}
    ``price`` is in kopecks for MoySklad (multiply rubles by 100 upstream).
    """
    positions: list[dict[str, Any]] = []
    for row in rows:
        positions.append(
            {
                "quantity": row.get("quantity", 1),
                "price": row.get("price", 0),
                "assortment": meta_ref(base_url, "product", str(row["ms_product_id"])),
            }
        )
    return positions
