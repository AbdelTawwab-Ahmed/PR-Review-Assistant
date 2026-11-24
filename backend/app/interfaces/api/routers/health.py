# pyright: reportMissingImports=false
from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings
from app.interfaces.api.deps import CacheDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(cache: CacheDep) -> dict[str, str]:
    cache_up = await cache.ping()
    return {"status": "ok" if cache_up else "degraded", "cache": "up" if cache_up else "down"}


@router.get("/health/llm")
async def llm_health() -> dict[str, Any]:
    """Report non-secret LLM configuration status for deployment diagnostics."""
    settings = get_settings()
    has_endpoint = bool(settings.azure_openai_endpoint)
    has_api_key = bool(settings.azure_openai_api_key.get_secret_value())
    has_strong = bool(settings.azure_openai_deployment_strong)
    return {
        "configured": has_endpoint and has_api_key and has_strong,
        "has_endpoint": has_endpoint,
        "has_api_key": has_api_key,
        "deployment_strong": settings.azure_openai_deployment_strong or None,
        "deployment_fast": settings.azure_openai_deployment_fast or None,
        "api_version": settings.azure_openai_api_version,
        "environment": settings.environment,
    }
