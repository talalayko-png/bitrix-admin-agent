"""Connector factory: returns mock or guarded-real clients based on settings.

Even when ``use_mock_connectors`` is False, the real clients are guarded by
``guard_egress`` and will refuse to call out unless all safety fuses allow it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.config import Settings


@dataclass
class Connectors:
    bitrix24: Any
    moysklad: Any


def build_connectors(settings: Settings) -> Connectors:
    if settings.use_mock_connectors:
        from src.connectors.bitrix24.mock import MockBitrix24Client
        from src.connectors.moysklad.mock import MockMoySkladClient

        return Connectors(
            bitrix24=MockBitrix24Client(),
            moysklad=MockMoySkladClient(),
        )

    from src.connectors.bitrix24.client import Bitrix24Client
    from src.connectors.moysklad.client import MoySkladClient

    return Connectors(
        bitrix24=Bitrix24Client(settings),
        moysklad=MoySkladClient(settings),
    )
