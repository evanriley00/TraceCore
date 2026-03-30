from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any


class RateLimitExceeded(Exception):
    pass


class _InMemoryTTLStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}
        self._lock = Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl_seconds, value)

    def incr(self, key: str, ttl_seconds: int) -> int:
        with self._lock:
            expires_at, raw_value = self._data.get(key, (0.0, "0"))
            if expires_at <= time.time():
                current_value = 0
            else:
                current_value = int(raw_value)
            current_value += 1
            self._data[key] = (time.time() + ttl_seconds, str(current_value))
            return current_value


class DecisionCache:
    def __init__(self, redis_url: str) -> None:
        self._redis = None
        self._memory = _InMemoryTTLStore()
        try:
            import redis

            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None

    @property
    def backend_name(self) -> str:
        return "redis" if self._redis is not None else "memory"

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw_value = self._redis.get(key) if self._redis is not None else self._memory.get(key)
        if raw_value is None:
            return None
        return json.loads(raw_value)

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        serialized = json.dumps(value)
        if self._redis is not None:
            self._redis.setex(key, ttl_seconds, serialized)
            return
        self._memory.set(key, serialized, ttl_seconds)

    def increment(self, key: str, ttl_seconds: int) -> int:
        if self._redis is not None:
            pipeline = self._redis.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, ttl_seconds)
            current, _ = pipeline.execute()
            return int(current)
        return self._memory.incr(key, ttl_seconds)

    def close(self) -> None:
        if self._redis is not None:
            self._redis.close()


class RateLimiter:
    def __init__(self, cache: DecisionCache, limit: int, window_seconds: int = 60) -> None:
        self.cache = cache
        self.limit = limit
        self.window_seconds = window_seconds

    def enforce(self, key: str) -> None:
        current = self.cache.increment(f"rate_limit:{key}", self.window_seconds)
        if current > self.limit:
            raise RateLimitExceeded(f"Rate limit exceeded for {key}")

