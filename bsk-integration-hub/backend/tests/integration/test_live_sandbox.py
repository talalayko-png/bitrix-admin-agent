"""Live sandbox integration tests — SKIPPED by default.

These make REAL calls to Bitrix24 / MoySklad sandboxes and therefore require:
  * BSK_LIVE_TESTS=1
  * ALLOW_REAL_API=true, USE_MOCK_CONNECTORS=false, DRY_RUN=false
  * valid BITRIX24_OUTBOUND_WEBHOOK_URL / MOYSKLAD_TOKEN credentials.

Without those they are skipped, so CI and local runs stay offline and safe.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("BSK_LIVE_TESTS") != "1",
    reason="live sandbox tests disabled (set BSK_LIVE_TESTS=1 + real credentials)",
)


def test_moysklad_sandbox_smoke():
    from src.config import get_settings
    from src.connectors.moysklad.client import MoySkladClient

    client = MoySkladClient(get_settings())
    # Should not raise against a real sandbox; returns None if not found.
    client.find_order_by_external("bsk-nonexistent-external-id")


def test_bitrix24_sandbox_smoke():
    from src.config import get_settings
    from src.connectors.bitrix24.client import Bitrix24Client

    client = Bitrix24Client(get_settings())
    # Reading a deal should succeed against a real sandbox webhook.
    client.get_deal(os.environ["BSK_LIVE_DEAL_ID"])
