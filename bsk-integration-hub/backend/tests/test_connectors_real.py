"""Real connectors exercised fully OFFLINE via httpx.MockTransport.

No network: a mock transport answers Bitrix24 / MoySklad requests. This proves
the real code paths (request building + response parsing + the workflow apply
path) without ever calling out, while the egress guard still blocks unless all
fuses are flipped.
"""

import json

import httpx
import pytest
from sqlalchemy import select

from src.config import Settings, reload_settings
from src.connectors.base import EgressBlockedError
from src.connectors.bitrix24.client import Bitrix24Client
from src.connectors.moysklad.client import MoySkladClient

B24_URL = "https://b24.example/rest/1/tok"
MS_URL = "https://ms.example/api/remap/1.2"


def _real_settings(**over) -> Settings:
    base = dict(
        allow_real_api=True,
        use_mock_connectors=False,
        dry_run=False,
        bitrix24_outbound_webhook_url=B24_URL,
        moysklad_base_url=MS_URL,
    )
    base.update(over)
    return Settings(**base)


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    path = url.split("?")[0]
    if "crm.deal.get" in url:
        return httpx.Response(
            200,
            json={
                "result": {
                    "ID": "555",
                    "TITLE": "Deal 555",
                    "STAGE_ID": "WON",
                    "OPPORTUNITY": "1000",
                    "CURRENCY_ID": "RUB",
                }
            },
        )
    if "crm.deal.productrows.get" in url:
        return httpx.Response(
            200,
            json={"result": [{"PRODUCT_NAME": "Widget", "PRICE": "500", "QUANTITY": "2"}]},
        )
    if path.endswith("/entity/customerorder") and request.method == "GET":
        return httpx.Response(200, json={"rows": []})
    if path.endswith("/entity/customerorder") and request.method == "POST":
        body = json.loads(request.content.decode() or "{}")
        return httpx.Response(200, json={"id": "ms-order-1", **body})
    return httpx.Response(404, json={"unmatched": url})


def test_guard_blocks_even_with_transport():
    # Safe (default) settings -> blocked no matter what transport is injected.
    client = MoySkladClient(Settings(), transport=httpx.MockTransport(_handler))
    with pytest.raises(EgressBlockedError):
        client.create_order({"name": "x"})


def test_bitrix24_client_offline():
    client = Bitrix24Client(_real_settings(), transport=httpx.MockTransport(_handler))
    assert client.get_deal("555")["ID"] == "555"
    assert client.get_deal_products("555")[0]["PRODUCT_NAME"] == "Widget"


def test_moysklad_client_offline():
    client = MoySkladClient(_real_settings(), transport=httpx.MockTransport(_handler))
    assert client.find_order_by_external("555") is None
    created = client.create_order({"externalCode": "555", "name": "Order"})
    assert created["id"] == "ms-order-1"
    assert created["externalCode"] == "555"


def test_readonly_mode_offline():
    """Real reads + dry-run: reads succeed, writes are blocked."""
    ro = _real_settings(dry_run=True)
    client = MoySkladClient(ro, transport=httpx.MockTransport(_handler))
    assert client.find_order_by_external("555") is None  # read allowed
    with pytest.raises(EgressBlockedError):
        client.create_order({"externalCode": "555"})  # write blocked


def test_supplier_doc_writes_blocked_in_dry_run():
    ro = _real_settings(dry_run=True)
    client = MoySkladClient(ro, transport=httpx.MockTransport(_handler))
    with pytest.raises(EgressBlockedError):
        client.create_purchaseorder({"name": "x"})


def test_secrets_not_in_recorded_calls():
    s = _real_settings(moysklad_token="SUPER_SECRET_TOKEN", dry_run=True)
    client = MoySkladClient(s, transport=httpx.MockTransport(_handler))
    client.find_order_by_external("555")
    assert "SUPER_SECRET_TOKEN" not in repr(client.calls)


def test_real_apply_path_offline(monkeypatch):
    """Run the full operation in REAL mode (dry_run off) against MockTransport."""
    monkeypatch.setenv("ALLOW_REAL_API", "true")
    monkeypatch.setenv("USE_MOCK_CONNECTORS", "false")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("BITRIX24_OUTBOUND_WEBHOOK_URL", B24_URL)
    monkeypatch.setenv("MOYSKLAD_BASE_URL", MS_URL)
    reload_settings()

    from src.connectors.factory import Connectors

    def fake_build(settings):
        transport = httpx.MockTransport(_handler)
        return Connectors(
            bitrix24=Bitrix24Client(settings, transport=transport),
            moysklad=MoySkladClient(settings, transport=transport),
        )

    monkeypatch.setattr("src.services.operations.build_connectors", fake_build)

    from src.db.base import session_scope
    from src.db.models import EntityLink, Operation
    from src.domain.entities import OperationDraft
    from src.services.operations import OperationService

    op_id = OperationService().create_and_enqueue(
        OperationDraft(
            type="deal_to_order",
            source="bitrix24",
            workflow_key="deal_to_order",
            idempotency_key="real-555",
            payload={"deal_id": "555", "stage": "WON"},
        )
    )

    with session_scope() as session:
        op = session.get(Operation, op_id)
        assert op.status == "succeeded"
        assert op.dry_run is False
        assert op.result["dry_run"] is False
        assert op.result["action"] == "create"
        links = session.execute(select(EntityLink)).scalars().all()
        assert any(link.ms_id == "ms-order-1" for link in links)
