from dataclasses import dataclass

from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.cache_port import CachePort
from app.application.use_cases.analyze_pull_request import AnalyzePullRequest
from app.application.use_cases.handle_pr_event import HandlePullRequestEvent
from app.application.use_cases.validate_pull_request import ValidatePullRequest
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.graph import build_analysis_graph
from app.core.config import Settings
from app.infrastructure.analyzers.bandit import BanditAnalyzer
from app.infrastructure.analyzers.ruff import RuffAnalyzer
from app.infrastructure.analyzers.semgrep import SemgrepAnalyzer
from app.infrastructure.cache.cache import build_cache
from app.infrastructure.dispatch.logging_dispatcher import LoggingRunDispatcher
from app.infrastructure.github.client import GitHubClient
from app.infrastructure.llm.azure_openai import AzureOpenAILLM
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.llm.token_tracker import TokenTracker
from app.infrastructure.sandbox.docker_sandbox import DockerSandbox, SandboxLimits
from app.infrastructure.sandbox.pytest_runner import PytestRunner
from app.infrastructure.sandbox.workspace import WorkspaceFactory


@dataclass
class Container:
    cache: CachePort
    github: GitHubClient
    handle_pr_event: HandlePullRequestEvent
    analysis: AnalyzePullRequest
    token_tracker: TokenTracker
    validation: ValidatePullRequest | None = None

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

    workspaces: WorkspaceFactory | None = None
    analyzers: tuple[AnalyzerPort, ...] = ()
    validation: ValidatePullRequest | None = None
    if settings.sandbox_enabled:
        sandbox = DockerSandbox(
            image=settings.sandbox_image,
            limits=SandboxLimits(
                memory_mb=settings.sandbox_memory_mb,
                cpus=settings.sandbox_cpus,
                pids=settings.sandbox_pids_limit,
                timeout_seconds=settings.sandbox_timeout_seconds,
            ),
            max_concurrency=settings.sandbox_max_concurrency,
        )
        workspaces = WorkspaceFactory(
            github,
            max_archive_mb=settings.sandbox_workspace_max_mb,
            max_files=settings.sandbox_max_files,
        )
        analyzers = (RuffAnalyzer(sandbox), BanditAnalyzer(sandbox), SemgrepAnalyzer(sandbox))
        validation = ValidatePullRequest(
            github,
            workspaces,
            analyzers,
            PytestRunner(sandbox, timeout_seconds=settings.sandbox_test_timeout_seconds),
            max_files=settings.sandbox_max_analyzed_files,
        )

    graph = build_analysis_graph(
        WorkflowDeps(
            github=github,
            llm=llm,
            chunk_chars=settings.review_chunk_chars,
            max_chunks=settings.review_max_chunks,
            workspaces=workspaces,
            analyzers=analyzers,
            max_analyzed_files=settings.sandbox_max_analyzed_files,
        )
    )
    return Container(
        cache=cache,
        github=github,
        handle_pr_event=handle_pr_event,
        analysis=AnalyzePullRequest(graph),
        token_tracker=tracker,
        validation=validation,
    )
