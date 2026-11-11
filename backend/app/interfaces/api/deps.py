from typing import Annotated

from fastapi import Depends, Request  # type: ignore[import-not-found]

from app.application.ports.cache_port import CachePort


def get_cache(request: Request) -> CachePort:
    return request.app.state.cache


CacheDep = Annotated[CachePort, Depends(get_cache)]
