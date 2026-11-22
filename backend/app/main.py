import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.container import build_container
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.interfaces.api.routers import approvals, dev, health, repos, runs, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    container = build_container(settings)
    app.state.container = container
    app.state.cache = container.cache

    await container.checkpointer_manager.setup()
    if container.db_manager is not None:
        await container.db_manager.setup()

    monitor_task = None
    if container.repo_monitor is not None:
        monitor_task = asyncio.create_task(container.repo_monitor.run_loop())

    try:
        yield
    finally:
        if monitor_task is not None:
            monitor_task.cancel()
        await container.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def app_insights_telemetry_middleware(request: Request, call_next):
        start_time = time.time()
        error_msg = None
        response = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error_msg = str(exc)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            container = getattr(request.app.state, "container", None)
            if container and container.telemetry and container.telemetry.is_enabled:
                status_code = response.status_code if response else 500
                container.telemetry.track_request(
                    name=f"{request.method} {request.url.path}",
                    url=str(request.url),
                    duration_ms=duration_ms,
                    status_code=status_code,
                    success=(status_code < 400 and error_msg is None),
                    error=error_msg,
                )

    register_error_handlers(app)

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(webhooks.router, prefix=settings.api_prefix)
    app.include_router(approvals.router, prefix=settings.api_prefix)
    app.include_router(runs.router, prefix=settings.api_prefix)
    app.include_router(repos.router, prefix=settings.api_prefix)

    if settings.environment == "development":
        app.include_router(dev.router, prefix=settings.api_prefix)

    return app


app = create_app()
