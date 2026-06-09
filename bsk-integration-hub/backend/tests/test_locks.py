import fakeredis
import pytest

from src.queue.locks import LockNotAcquired, redis_lock


def test_lock_is_mutually_exclusive():
    client = fakeredis.FakeStrictRedis()
    with redis_lock(client, "lock:op:abc", 5000):
        with pytest.raises(LockNotAcquired):
            with redis_lock(client, "lock:op:abc", 5000):
                pass


def test_lock_released_after_use():
    client = fakeredis.FakeStrictRedis()
    with redis_lock(client, "lock:op:abc", 5000):
        pass
    # lock free again
    with redis_lock(client, "lock:op:abc", 5000):
        pass
    assert client.get("lock:op:abc") is None
