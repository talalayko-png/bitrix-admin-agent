"""Exponential backoff helpers."""

from __future__ import annotations


def backoff_delay(attempt: int, base_seconds: int, cap_seconds: int) -> int:
    """Exponential backoff for a 1-based attempt number.

    attempt=1 -> base, attempt=2 -> base*2, attempt=3 -> base*4, ... capped.
    """
    attempt = max(1, attempt)
    delay = base_seconds * (2 ** (attempt - 1))
    return int(min(cap_seconds, delay))


def backoff_schedule(max_retries: int, base_seconds: int, cap_seconds: int) -> list[int]:
    """Precomputed interval list (used by RQ Retry)."""
    return [backoff_delay(i, base_seconds, cap_seconds) for i in range(1, max_retries + 1)]
