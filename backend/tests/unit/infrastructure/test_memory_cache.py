from app.infrastructure.cache.memory_cache import InMemoryCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_roundtrip() -> None:
    cache = InMemoryCache()
    await cache.set("k", {"a": [1, 2]})
    assert await cache.get("k") == {"a": [1, 2]}


async def test_miss_returns_none() -> None:
    assert await InMemoryCache().get("missing") is None


async def test_entry_expires_after_ttl() -> None:
    clock = FakeClock()
    cache = InMemoryCache(clock=clock)
    await cache.set("k", "v", ttl_seconds=10)
    clock.now = 9.9
    assert await cache.get("k") == "v"
    clock.now = 10
    assert await cache.get("k") is None


async def test_delete() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v")
    await cache.delete("k")
    assert await cache.get("k") is None


async def test_oldest_entry_is_evicted_at_capacity() -> None:
    cache = InMemoryCache(max_items=2)
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.set("c", 3)
    assert await cache.get("a") is None
    assert await cache.get("c") == 3


async def test_non_json_value_is_rejected() -> None:
    try:
        await InMemoryCache().set("k", object())
    except TypeError:
        return
    raise AssertionError("Expected TypeError for a non-JSON value")
