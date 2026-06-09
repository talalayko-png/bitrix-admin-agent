"""Distributed operation locks.

In ``redis`` queue mode, an operation is guarded by a Redis ``SET NX PX`` lock so
two workers can never execute the same operation concurrently. In ``sync`` mode
execution is inline and single-threaded, so the lock is a no-op (``nullcontext``).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any

from src.config import Settings


class LockNotAcquired(RuntimeError):
    """Raised when the operation lock is already held by someone else."""


@contextmanager
def redis_lock(client: Any, key: str, ttl_ms: int) -> Iterator[str]:
    token = uuid.uuid4().hex
    acquired = client.set(key, token, nx=True, px=ttl_ms)
    if not acquired:
        raise LockNotAcquired(key)
    try:
        yield token
    finally:
        # best-effort release, only if we still own the lock
        try:
            current = client.get(key)
            if current in (token, token.encode()):
                client.delete(key)
        except Exception:  # pragma: no cover - release is best effort
            pass


def operation_lock(
    settings: Settings, operation_key: str, client: Any | None = None
) -> AbstractContextManager:
    if settings.queue_backend != "redis":
        return nullcontext()
    if client is None:
        from src.queue.connection import get_redis

        client = get_redis()
    key = f"lock:op:{operation_key}"
    return redis_lock(client, key, settings.operation_lock_ttl_seconds * 1000)
