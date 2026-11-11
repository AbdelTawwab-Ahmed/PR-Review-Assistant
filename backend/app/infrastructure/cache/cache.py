from app.application.ports.cache_port import CachePort
from app.core.config import Settings
from app.infrastructure.cache.memory_cache import InMemoryCache
from app.infrastructure.cache.redis_cache import RedisCache


def build_cache(settings: Settings) -> CachePort:
    if settings.cache_backend == "memory":
        return InMemoryCache()
    return RedisCache.from_url(settings.redis_url)
