from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.container import build_container
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.interfaces.api.routers import health, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = build_container(settings)
    app.state.container = container
    app.state.cache = container.cache
    try:
        yield
    finally:
        await container.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(webhooks.router, prefix=settings.api_prefix)
    return app


app = create_app()
