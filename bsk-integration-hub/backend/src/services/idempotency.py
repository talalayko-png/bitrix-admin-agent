"""Idempotency key helpers."""

from __future__ import annotations

from src.utils.ids import stable_key


def idempotency_key(*parts: object) -> str:
    """Build a deterministic idempotency key from parts.

    The same source event always produces the same key, so a repeated webhook
    maps to the existing operation instead of creating a duplicate.
    """
    return stable_key(*parts)
