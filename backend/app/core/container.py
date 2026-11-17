from dataclasses import dataclass

from app.application.ports.cache_port import CachePort
from app.application.use_cases.analyze_pull_request import AnalyzePullRequest
from app.application.use_cases.handle_pr_event import HandlePullRequestEvent
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.graph import build_analysis_graph
from app.core.config import Settings
from app.infrastructure.cache.cache import build_cache
from app.infrastructure.dispatch.logging_dispatcher import LoggingRunDispatcher
from app.infrastructure.github.client import GitHubClient
from app.infrastructure.llm.azure_openai import AzureOpenAILLM
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.llm.token_tracker import TokenTracker


@dataclass
class Container:
    cache: CachePort
    github: GitHubClient
    handle_pr_event: HandlePullRequestEvent
    analysis: AnalyzePullRequest
    token_tracker: TokenTracker

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

    tracker = TokenTracker()
    llm = AzureOpenAILLM(
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        router=ModelRouter(
            strong=settings.azure_openai_deployment_strong,
            fast=settings.azure_openai_deployment_fast,
        ),
        tracker=tracker,
        timeout_seconds=settings.llm_timeout_seconds,
        max_concurrency=settings.llm_max_concurrency,
    )
    graph = build_analysis_graph(
        WorkflowDeps(
            github=github,
            llm=llm,
            chunk_chars=settings.review_chunk_chars,
            max_chunks=settings.review_max_chunks,
        )
    )
    return Container(
        cache=cache,
        github=github,
        handle_pr_event=handle_pr_event,
        analysis=AnalyzePullRequest(graph),
        token_tracker=tracker,
    )