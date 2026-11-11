from collections.abc import Awaitable, Callable
from typing import Any

from app.application.ports.cache_port import CachePort


def pr_diff_key(repo: str, sha: str) -> str:
    return f"diff:{repo.lower()}:{sha}"


def analysis_key(repo: str, sha: str, analysis: str, version: str = "v1") -> str:
    """Bump `version` when prompts or models change, so old results are not reused."""
    return f"analysis:{version}:{analysis}:{repo.lower()}:{sha}"


async def get_or_compute(
    cache: CachePort,
    key: str,
    producer: Callable[[], Awaitable[Any]],
    ttl_seconds: int | None = None,
) -> Any:
    cached = await cache.get(key)
    if cached is not None:
        return cached
    value = await producer()
    if value is not None:
        await cache.set(key, value, ttl_seconds)
    return value
