# pyright: reportMissingImports=false
from fastapi import APIRouter

from app.interfaces.api.deps import CacheDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(cache: CacheDep) -> dict[str, str]:
    cache_up = await cache.ping()
    return {"status": "ok" if cache_up else "degraded", "cache": "up" if cache_up else "down"}
