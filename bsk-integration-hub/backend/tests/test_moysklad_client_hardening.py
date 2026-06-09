"""Hardened MoySklad client behaviors, fully offline via httpx.MockTransport."""

import httpx
import pytest

from src.config import Settings
from src.connectors.moysklad.client import MoySkladClient
from src.connectors.moysklad.errors import MoySkladError, MoySkladRateLimited
from src.connectors.moysklad.meta import meta_ref, positions_payload

MS_URL = "https://ms.example/api/remap/1.2"


def _settings(**over) -> Settings:
    base = dict(
        allow_real_api=True,
        use_mock_connectors=False,
        dry_run=False,
        moysklad_base_url=MS_URL,
        moysklad_backoff_base_seconds=0.0,  # no real sleeping in tests
    )
    base.update(over)
    return Settings(**base)


def test_meta_ref_and_positions():
    ref = meta_ref(MS_URL, "organization", "org-1")
    assert ref["meta"]["href"].endswith("/entity/organization/org-1")
    assert ref["meta"]["type"] == "organization"

    pos = positions_payload(MS_URL, [{"ms_product_id": "p1", "quantity": 2, "price": 100}])
    assert pos[0]["quantity"] == 2
    assert pos[0]["assortment"]["meta"]["href"].endswith("/entity/product/p1")


def test_retry_on_429_then_success():
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "customerorder" in str(request.url):
            state["n"] += 1
            if state["n"] == 1:
                return httpx.Response(
                    429,
                    headers={"X-RateLimit-Retry-After": "0"},
                    json={"errors": [{"error": "rate", "code": 1049}]},
                )
            return httpx.Response(200, json={"rows": [{"id": "o1"}], "meta": {"size": 1}})
        return httpx.Response(404, json={})

    client = MoySkladClient(_settings(), transport=httpx.MockTransport(handler))
    assert client.find_order_by_external("X")["id"] == "o1"
    assert state["n"] == 2  # one retry happened


def test_429_exhausted_raises_rate_limited():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"X-RateLimit-Retry-After": "0"}, json={"errors": []})

    client = MoySkladClient(
        _settings(moysklad_max_retries=2), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(MoySkladRateLimited):
        client.find_order_by_external("X")


def test_error_normalization():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": [{"error": "bad request", "code": 42}]})

    client = MoySkladClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(MoySkladError) as exc:
        client.create_order({"x": 1})
    assert exc.value.status == 400
    assert "bad request" in str(exc.value)


def test_pagination_aggregates_pages():
    pages = {0: [{"id": "1"}, {"id": "2"}], 2: [{"id": "3"}, {"id": "4"}], 4: [{"id": "5"}]}

    def handler(request: httpx.Request) -> httpx.Response:
        if "organization" in str(request.url):
            offset = int(dict(request.url.params).get("offset", "0"))
            return httpx.Response(200, json={"rows": pages.get(offset, []), "meta": {"size": 5}})
        return httpx.Response(404, json={})

    client = MoySkladClient(
        _settings(moysklad_page_limit=2), transport=httpx.MockTransport(handler)
    )
    assert [o["id"] for o in client.list_organizations()] == ["1", "2", "3", "4", "5"]
