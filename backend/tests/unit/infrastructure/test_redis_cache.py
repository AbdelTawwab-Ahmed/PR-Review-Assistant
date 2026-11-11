import pytest
from fakeredis import FakeAsyncRedis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.infrastructure.cache.redis_cache import RedisCache


@pytest.fixture
async def client():
    redis = FakeAsyncRedis(decode_responses=True)
    yield redis
    await redis.aclose()


async def test_roundtrip_and_prefix(client) -> None:
    cache = RedisCache(client)
    await cache.set("k", {"a": 1})
    assert await cache.get("k") == {"a": 1}
    assert await client.get("prra:k") is not None


async def test_ttl_is_applied(client) -> None:
    cache = RedisCache(client)
    await cache.set("k", "v", ttl_seconds=60)
    assert await client.ttl("prra:k") > 0


async def test_delete_and_ping(client) -> None:
    cache = RedisCache(client)
    await cache.set("k", "v")
    await cache.delete("k")
    assert await cache.get("k") is None
    assert await cache.ping() is True


async def test_invalid_json_is_a_miss(client) -> None:
    await client.set("prra:k", "not-json")
    assert await RedisCache(client).get("k") is None


class BrokenRedis:
    async def get(self, *args, **kwargs):
        raise RedisConnectionError("down")

    async def set(self, *args, **kwargs):
        raise RedisConnectionError("down")

    async def delete(self, *args, **kwargs):
        raise RedisConnectionError("down")

    async def ping(self, *args, **kwargs):
        raise RedisConnectionError("down")

    async def aclose(self) -> None:
        return None


async def test_redis_outage_fails_open() -> None:
    cache = RedisCache(BrokenRedis())
    assert await cache.get("k") is None
    await cache.set("k", "v")
    await cache.delete("k")
    assert await cache.ping() is False
