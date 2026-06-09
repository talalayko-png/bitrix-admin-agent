"""Time helpers (timezone-naive UTC for cross-db consistency)."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC timestamp (consistent across SQLite and Postgres)."""
    return datetime.now(UTC).replace(tzinfo=None)
