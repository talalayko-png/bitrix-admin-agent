"""Connector base utilities and the egress safety guard.

Every real outbound call MUST go through ``guard_egress``. It raises unless all
three safety fuses agree (see SECURITY.md). This guarantees the MVP never calls
Bitrix24 / MoySklad for real, even if a real client is accidentally wired in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import Settings


class EgressBlockedError(RuntimeError):
    """Raised when an outbound call is attempted while a safety fuse is active."""


def guard_egress(settings: Settings, what: str) -> None:
    if not settings.real_api_enabled:
        raise EgressBlockedError(
            f"Outbound call blocked: {what}. Real API is disabled "
            f"(allow_real_api={settings.allow_real_api}, "
            f"use_mock_connectors={settings.use_mock_connectors}, "
            f"dry_run={settings.dry_run}). All three fuses must allow real calls."
        )


@dataclass
class RecordedCall:
    method: str
    args: dict[str, Any] = field(default_factory=dict)


class CallRecorder:
    """Mixin that records calls so dry-run / tests can assert on them."""

    def __init__(self) -> None:
        self.calls: list[RecordedCall] = []

    def _record(self, method: str, **args: Any) -> None:
        self.calls.append(RecordedCall(method=method, args=args))
