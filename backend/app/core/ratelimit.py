"""Fixed-window rate limiter. In-process by default; for multi-instance deployments set
RATE_LIMIT_REDIS_URL and the Redis backend is used instead so limits are shared."""
from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request

from app.core.audit import client_ip


class _MemoryBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, tuple[int, float]] = {}

    def hit(self, key: str, window: int) -> int:
        now = time.time()
        with self._lock:
            count, start = self._hits.get(key, (0, now))
            if now - start >= window:
                count, start = 0, now
            count += 1
            self._hits[key] = (count, start)
            if len(self._hits) > 50_000:  # crude memory bound
                self._hits = {k: v for k, v in self._hits.items() if now - v[1] < window}
            return count

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class _RedisBackend:
    def __init__(self, url: str) -> None:
        import redis  # optional dependency

        self._r = redis.Redis.from_url(url)

    def hit(self, key: str, window: int) -> int:
        bucket = f"rl:{key}:{int(time.time() // window)}"
        pipe = self._r.pipeline()
        pipe.incr(bucket)
        pipe.expire(bucket, window)
        return int(pipe.execute()[0])

    def reset(self) -> None:  # pragma: no cover
        pass


_backend = _RedisBackend(os.environ["RATE_LIMIT_REDIS_URL"]) if os.environ.get("RATE_LIMIT_REDIS_URL") else _MemoryBackend()


def enforce(request: Request, scope: str, limit: int, window_seconds: int = 60, key_suffix: str = "") -> None:
    key = f"{scope}:{client_ip(request)}:{key_suffix}"
    if _backend.hit(key, window_seconds) > limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment and try again.")


def reset_all() -> None:
    _backend.reset()
