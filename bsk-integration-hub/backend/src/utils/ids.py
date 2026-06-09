"""Identifier / key helpers."""

from __future__ import annotations

import hashlib
import uuid


def new_id() -> str:
    return uuid.uuid4().hex


def stable_key(*parts: object) -> str:
    """Deterministic key from parts, e.g. for idempotency keys."""
    raw = ":".join(str(p) for p in parts)
    return raw


def hashed_key(*parts: object) -> str:
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
