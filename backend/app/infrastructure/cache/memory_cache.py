import json
import time
from collections.abc import Callable
from typing import Any


class InMemoryCache:
    """Process-local cache for tests and local runs without Redis."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_items: int = 1024,
    ) -> None:
        self._clock = clock
        self._max_items = max_items
        self._data: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        payload, expires_at = entry
        if expires_at is not None and self._clock() >= expires_at:
            del self._data[key]
            return None
        return json.loads(payload)

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(value)  # same JSON-only rule as the Redis adapter
        if key not in self._data and len(self._data) >= self._max_items:
            self._data.pop(next(iter(self._data)))  # evict the oldest entry
        expires_at = None if ttl_seconds is None else self._clock() + ttl_seconds
        self._data[key] = (payload, expires_at)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()
