"""The MVP must never call out. These tests lock that behavior in."""

import pytest

from src.config import Settings, get_settings
from src.connectors.base import EgressBlockedError, guard_egress


def test_real_api_disabled_by_default():
    assert get_settings().real_api_enabled is False


def test_guard_blocks_by_default():
    with pytest.raises(EgressBlockedError):
        guard_egress(get_settings(), "any.call")


def test_all_three_fuses_required():
    # only when all three agree is real egress allowed
    ok = Settings(allow_real_api=True, use_mock_connectors=False, dry_run=False)
    assert ok.real_api_enabled is True
    guard_egress(ok, "allowed.call")  # must not raise

    for blocked in (
        Settings(allow_real_api=False, use_mock_connectors=False, dry_run=False),
        Settings(allow_real_api=True, use_mock_connectors=True, dry_run=False),
        Settings(allow_real_api=True, use_mock_connectors=False, dry_run=True),
    ):
        assert blocked.real_api_enabled is False
        with pytest.raises(EgressBlockedError):
            guard_egress(blocked, "blocked.call")


def test_real_moysklad_client_refuses_to_call():
    from src.connectors.moysklad.client import MoySkladClient

    client = MoySkladClient(get_settings())
    with pytest.raises(EgressBlockedError):
        client.create_order({"name": "x"})
