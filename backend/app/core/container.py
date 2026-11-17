from dataclasses import dataclass

from app.application.ports.cache_port import CachePort
from app.application.use_cases.handle_pr_event import HandlePullRequestEvent
from app.core.config import Settings
from app.infrastructure.cache.cache import build_cache
from app.infrastructure.dispatch.logging_dispatcher import LoggingRunDispatcher
from app.infrastructure.github.client import GitHubClient


@dataclass
class Container:
    cache: CachePort
    github: GitHubClient
    handle_pr_event: HandlePullRequestEvent

    async def aclose(self) -> None:
        await self.github.aclose()
        await self.cache.close()


def build_container(settings: Settings) -> Container:
    cache = build_cache(settings)
    github = GitHubClient(
        token=settings.github_token.get_secret_value(),
        api_url=settings.github_api_url,
        cache=cache,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )
    handle_pr_event = HandlePullRequestEvent(
        cache,
        LoggingRunDispatcher(),
        bot_login=settings.github_bot_login,
        dedup_ttl_seconds=settings.cache_ttl_seconds,
    )
    return Container(cache=cache, github=github, handle_pr_event=handle_pr_event)
