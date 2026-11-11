import importlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _is_redis_error(error: Exception) -> bool:
    try:
        redis_exceptions = importlib.import_module("redis.exceptions")
    except ImportError:
        return False
    return isinstance(error, redis_exceptions.RedisError)


class RedisCache:
    """Redis-backed cache. Redis failures are logged and treated as cache misses,
    so a Redis outage slows the pipeline down but never breaks it."""

    def __init__(self, client: Any, key_prefix: str = "prra:") -> None:
        self._client = client
        self._prefix = key_prefix

    @classmethod
    def from_url(cls, url: str, key_prefix: str = "prra:") -> "RedisCache":
        redis_asyncio = importlib.import_module("redis.asyncio")
        client = redis_asyncio.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        return cls(client, key_prefix)

    def _k(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(self._k(key))
        except Exception as exc:
            if not _is_redis_error(exc):
                raise
            logger.warning("cache get failed for %s", key, exc_info=True)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            logger.warning("cache value for %s is not valid JSON", key)
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(value)
        try:
            await self._client.set(self._k(key), payload, ex=ttl_seconds)
        except Exception as exc:
            if not _is_redis_error(exc):
                raise
            logger.warning("cache set failed for %s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(self._k(key))
        except Exception as exc:
            if not _is_redis_error(exc):
                raise
            logger.warning("cache delete failed for %s", key, exc_info=True)

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception as exc:
            if not _is_redis_error(exc):
                raise
            return False

    async def close(self) -> None:
        await self._client.aclose()
