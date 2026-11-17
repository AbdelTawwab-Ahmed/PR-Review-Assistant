
from typing import Annotated

from fastapi import Depends, Request

from app.application.ports.cache_port import CachePort
from app.application.use_cases.handle_pr_event import HandlePullRequestEvent
from app.core.config import Settings, get_settings
from app.core.container import Container
from app.core.errors import UnauthorizedError
from app.infrastructure.github.webhook_signature import verify_signature


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_cache(request: Request) -> CachePort:
    return request.app.state.cache


def get_handle_pr_event(
    container: Annotated[Container, Depends(get_container)],
) -> HandlePullRequestEvent:
    return container.handle_pr_event


CacheDep = Annotated[CachePort, Depends(get_cache)]

HandlePREventDep = Annotated[
    HandlePullRequestEvent,
    Depends(get_handle_pr_event),
]


async def get_github_body(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> bytes:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_signature(
        settings.github_webhook_secret.get_secret_value(),
        body,
        signature,
    ):
        raise UnauthorizedError("Invalid webhook signature")

    return body


GitHubBodyDep = Annotated[bytes, Depends(get_github_body)]