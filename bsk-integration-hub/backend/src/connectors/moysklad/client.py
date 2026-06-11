"""Real MoySklad client (guarded, hardened).

Adds: retry/backoff with 429 (rate-limit) handling, pagination, normalized
errors, and reference/document entities used by the supplier-docs workflow.

Reads are gated by ``guard_read`` (allowed in 'real reads + dry-run'); writes by
``guard_write`` (require dry-run off). A custom ``httpx`` transport can be
injected for offline tests.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from src.config import Settings
from src.connectors.base import CallRecorder, guard_read, guard_write
from src.connectors.moysklad.errors import MoySkladError, MoySkladRateLimited


class MoySkladClient(CallRecorder):
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._base = settings.moysklad_base_url.rstrip("/")
        self._transport = transport
        self._max_retries = settings.moysklad_max_retries
        self._backoff_base = settings.moysklad_backoff_base_seconds
        self._page_limit = settings.moysklad_page_limit

    # ------------------------------------------------------------------ http
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.moysklad_token}",
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=30, transport=self._transport, headers=self._headers())

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except Exception:  # pragma: no cover - non-JSON error body
            return {}

    def _retry_after(self, resp: httpx.Response, attempt: int) -> float:
        # MoySklad uses X-RateLimit-Retry-After (ms); fall back to Retry-After (s).
        raw_ms = resp.headers.get("X-RateLimit-Retry-After")
        if raw_ms:
            try:
                return float(raw_ms) / 1000.0
            except ValueError:
                pass
        raw_s = resp.headers.get("Retry-After")
        if raw_s:
            try:
                return float(raw_s)
            except ValueError:
                pass
        return self._backoff(attempt)

    def _backoff(self, attempt: int) -> float:
        return self._backoff_base * (2 ** (attempt - 1))

    @staticmethod
    def _sleep(seconds: float) -> None:
        if seconds and seconds > 0:
            time.sleep(seconds)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if not self._base:
            raise RuntimeError("moysklad: MOYSKLAD_BASE_URL не задан (пустой базовый URL)")
        url = f"{self._base}{path}"
        attempt = 0
        while True:
            attempt += 1
            try:
                with self._client() as client:
                    resp = client.request(method, url, params=params, json=json)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"moysklad {method} {path}: {exc}") from exc
            status = resp.status_code
            if status == 429 and attempt <= self._max_retries:
                self._sleep(self._retry_after(resp, attempt))
                continue
            if status >= 500 and attempt <= self._max_retries:
                self._sleep(self._backoff(attempt))
                continue
            if status == 429:
                raise MoySkladRateLimited(self._retry_after(resp, attempt), self._safe_json(resp))
            if status >= 400:
                raise MoySkladError.from_response(status, self._safe_json(resp))
            return self._safe_json(resp)

    def _list(self, entity: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Paginate an entity list endpoint and return all rows."""
        query = dict(params or {})
        query["limit"] = self._page_limit
        offset = 0
        rows: list[dict[str, Any]] = []
        while True:
            query["offset"] = offset
            data = self._request("GET", f"/entity/{entity}", params=query)
            chunk = data.get("rows", []) if isinstance(data, dict) else []
            rows.extend(chunk)
            size = len(rows)
            if isinstance(data, dict):
                size = data.get("meta", {}).get("size", len(rows))
            offset += len(chunk)
            if not chunk or offset >= size or len(chunk) < self._page_limit:
                break
        return rows

    def _find_by_external(self, entity: str, external_id: str) -> dict[str, Any] | None:
        rows = self._list(entity, {"filter": f"externalCode={external_id}"})
        return rows[0] if rows else None

    # ---------------------------------------------------------- references
    def list_organizations(self) -> list[dict[str, Any]]:
        guard_read(self._settings, "moysklad.list_organizations")
        self._record("list_organizations")
        return self._list("organization")

    def find_organization(self, name: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_organization")
        self._record("find_organization", name=name)
        rows = self._list("organization", {"filter": f"name={name}"})
        return rows[0] if rows else None

    def list_stores(self) -> list[dict[str, Any]]:
        guard_read(self._settings, "moysklad.list_stores")
        self._record("list_stores")
        return self._list("store")

    def find_store(self, name: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_store")
        self._record("find_store", name=name)
        rows = self._list("store", {"filter": f"name={name}"})
        return rows[0] if rows else None

    # ---------------------------------------------------------- customer orders
    def find_order_by_external(self, external_id: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_order_by_external")
        self._record("find_order_by_external", external_id=external_id)
        return self._find_by_external("customerorder", external_id)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_order")
        self._record("create_order", payload=payload)
        return self._request("POST", "/entity/customerorder", json=payload)

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.update_order")
        self._record("update_order", order_id=order_id, payload=payload)
        return self._request("PUT", f"/entity/customerorder/{order_id}", json=payload)

    # ---------------------------------------------------------- counterparties
    def find_counterparty_by_external(self, external_id: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_counterparty_by_external")
        self._record("find_counterparty_by_external", external_id=external_id)
        return self._find_by_external("counterparty", external_id)

    def search_counterparties(self, query: str) -> list[dict[str, Any]]:
        guard_read(self._settings, "moysklad.search_counterparties")
        self._record("search_counterparties", query=query)
        return self._list("counterparty", {"search": query})

    def create_counterparty(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_counterparty")
        self._record("create_counterparty", payload=payload)
        return self._request("POST", "/entity/counterparty", json=payload)

    def update_counterparty(self, cp_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.update_counterparty")
        self._record("update_counterparty", cp_id=cp_id, payload=payload)
        return self._request("PUT", f"/entity/counterparty/{cp_id}", json=payload)

    # ---------------------------------------------------------- products
    def find_product_by_external(self, external_id: str) -> dict[str, Any] | None:
        guard_read(self._settings, "moysklad.find_product_by_external")
        self._record("find_product_by_external", external_id=external_id)
        return self._find_by_external("product", external_id)

    def find_products_by_code(self, code: str) -> list[dict[str, Any]]:
        guard_read(self._settings, "moysklad.find_products_by_code")
        self._record("find_products_by_code", code=code)
        return self._list("product", {"filter": f"code={code}"})

    def search_products(self, query: str) -> list[dict[str, Any]]:
        guard_read(self._settings, "moysklad.search_products")
        self._record("search_products", query=query)
        return self._list("product", {"search": query})

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_product")
        self._record("create_product", payload=payload)
        return self._request("POST", "/entity/product", json=payload)

    def update_product(self, product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.update_product")
        self._record("update_product", product_id=product_id, payload=payload)
        return self._request("PUT", f"/entity/product/{product_id}", json=payload)

    # ---------------------------------------------------------- supplier docs
    def create_purchaseorder(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_purchaseorder")
        self._record("create_purchaseorder", payload=payload)
        return self._request("POST", "/entity/purchaseorder", json=payload)

    def create_invoicein(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_invoicein")
        self._record("create_invoicein", payload=payload)
        return self._request("POST", "/entity/invoicein", json=payload)

    def create_supply(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_supply")
        self._record("create_supply", payload=payload)
        return self._request("POST", "/entity/supply", json=payload)

    # ---------------------------------------------------------- payments
    def create_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        guard_write(self._settings, "moysklad.create_payment")
        self._record("create_payment", payload=payload)
        return self._request("POST", "/entity/paymentin", json=payload)
