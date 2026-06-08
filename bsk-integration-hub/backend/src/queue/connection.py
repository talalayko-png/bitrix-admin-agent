"""Redis connection (lazy)."""

from __future__ import annotations

import redis

from src.config import get_settings

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(get_settings().redis_url)
    return _redis


def reset_redis() -> None:
    global _redis
    _redis = None
