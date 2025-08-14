import os
import time
from typing import Optional


class TokenStore:
    def get(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        raise NotImplementedError


class InMemoryTokenStore(TokenStore):
    def __init__(self):
        # key -> (value, expire_at_epoch)
        self._data: dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> Optional[str]:
        item = self._data.get(key)
        if not item:
            return None
        value, expire_at = item
        if time.time() >= expire_at:
            # expired
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._data[key] = (value, time.time() + ttl_seconds)


class RedisTokenStore(TokenStore):
    def __init__(self, url: Optional[str] = None):
        url = url or os.getenv("REDIS_URL")
        if not url:
            raise RuntimeError("REDIS_URL not configured")
        try:
            import redis  # type: ignore
        except Exception as e:
            raise RuntimeError("redis-py not installed") from e
        self._redis = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Optional[str]:
        return self._redis.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._redis.setex(key, ttl_seconds, value)


