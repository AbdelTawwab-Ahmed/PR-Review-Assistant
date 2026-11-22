import logging
from dataclasses import dataclass
from typing import Any

from app.application.fix_engine import FixEngine, FixSettings
from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.cache_port import CachePort
from app.application.ports.repositories import ReviewRunRepository
from app.application.ports.sandbox_port import SandboxPort
from app.application.services.repo_monitor import RepoMonitorService
from app.application.use_cases.analyze_pull_request import AnalyzePullRequest
from app.application.use_cases.approve_run import ApproveRun
from app.application.use_cases.get_run_status import GetRunStatus
from app.application.use_cases.handle_pr_event import HandlePullRequestEvent
from app.application.use_cases.publish_fix import PublishFix
from app.application.use_cases.validate_pull_request import ValidatePullRequest
from app.application.workflow.agents.fixer import FixerAgent
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.graph import build_analysis_graph
from app.core.config import Settings
from app.infrastructure.analyzers.bandit import BanditAnalyzer
from app.infrastructure.analyzers.ruff import RuffAnalyzer
from app.infrastructure.analyzers.semgrep import SemgrepAnalyzer
from app.infrastructure.cache.cache import build_cache
from app.infrastructure.dispatch.asyncio_dispatcher import AsyncioRunDispatcher
from app.infrastructure.github.client import GitHubClient
from app.infrastructure.llm.azure_openai import AzureOpenAILLM
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.llm.token_tracker import TokenTracker
from app.infrastructure.observability.telemetry import (
    TelemetryManager,
    build_telemetry,
)
from app.infrastructure.persistence.checkpointer import CheckpointerManager, build_checkpointer
from app.infrastructure.persistence.database import DatabaseManager, build_database_manager
from app.infrastructure.persistence.repositories import build_review_run_repository
from app.infrastructure.sandbox.docker_sandbox import DockerSandbox, SandboxLimits
from app.infrastructure.sandbox.dynamic_sessions_sandbox import (
    DynamicSessionsConfig,
    DynamicSessionsSandbox,
)
from app.infrastructure.sandbox.pytest_runner import PytestRunner
from app.infrastructure.sandbox.workspace import WorkspaceFactory
from app.infrastructure.sandbox.workspace_files import WorkspaceFiles

logger = logging.getLogger(__name__)


@dataclass
class Container:
    cache: CachePort
    github: GitHubClient
    handle_pr_event: HandlePullRequestEvent
    analysis: AnalyzePullRequest
    token_tracker: TokenTracker
    checkpointer_manager: CheckpointerManager
    approve_run: ApproveRun
    get_run_status: GetRunStatus
    run_repository: ReviewRunRepository
    telemetry: TelemetryManager | None = None
    _dynamic_sessions: DynamicSessionsSandbox | None = None
    db_manager: DatabaseManager | None = None
    graph: Any = None
    validation: ValidatePullRequest | None = None
    publisher: PublishFix | None = None
    repo_monitor: RepoMonitorService | None = None

    async def aclose(self) -> None:
        if self.repo_monitor is not None:
            self.repo_monitor.stop()
        await self.github.aclose()
        await self.cache.close()
        await self.checkpointer_manager.aclose()
        if self.telemetry is not None:
            await self.telemetry.aclose()
        if self._dynamic_sessions is not None:
            await self._dynamic_sessions.aclose()
        if self.db_manager is not None:
            await self.db_manager.aclose()


def _build_sandbox(settings: Settings) -> SandboxPort:
    """Build the configured sandbox backend.

    When ``sandbox_backend`` is ``"dynamic_sessions"`` **and** the pool
    endpoint is configured, return a ``DynamicSessionsSandbox``.
    Otherwise fall back to ``DockerSandbox`` with a warning.
    """
    if settings.sandbox_backend == "dynamic_sessions":
        endpoint = settings.dynamic_sessions_pool_endpoint
        if endpoint:
            logger.info("using Azure Dynamic Sessions sandbox")
            return DynamicSessionsSandbox(
                DynamicSessionsConfig(
                    pool_endpoint=endpoint,
                    api_key=(settings.dynamic_sessions_api_key.get_secret_value()),
                    max_session_seconds=(settings.dynamic_sessions_max_session_seconds),
                    max_concurrency=(settings.sandbox_max_concurrency),
                ),
            )
        logger.warning(
            "sandbox_backend is 'dynamic_sessions' but "
            "DYNAMIC_SESSIONS_POOL_ENDPOINT is not set; "
            "falling back to Docker"
        )

    return DockerSandbox(
        image=settings.sandbox_image,
        limits=SandboxLimits(
            memory_mb=settings.sandbox_memory_mb,
            cpus=settings.sandbox_cpus,
            pids=settings.sandbox_pids_limit,
            timeout_seconds=settings.sandbox_timeout_seconds,
        ),
        max_concurrency=settings.sandbox_max_concurrency,
    )


def build_container(settings: Settings) -> Container:
    cache = build_cache(settings)
    github = GitHubClient(
        token=settings.github_token.get_secret_value(),
        api_url=settings.github_api_url,
        cache=cache,
        cache_ttl_seconds=settings.cache_ttl_seconds,
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

    workspaces = WorkspaceFactory(
        github,
        max_archive_mb=settings.sandbox_workspace_max_mb,
        max_files=settings.sandbox_max_files,
    )
    analyzers: tuple[AnalyzerPort, ...] = ()
    suite_runner: PytestRunner | None = None
    validation: ValidatePullRequest | None = None
    dynamic_sessions: DynamicSessionsSandbox | None = None
    if settings.sandbox_enabled:
        sandbox = _build_sandbox(settings)
        if isinstance(sandbox, DynamicSessionsSandbox):
            dynamic_sessions = sandbox
        analyzers = (
            RuffAnalyzer(sandbox),
            BanditAnalyzer(sandbox),
            SemgrepAnalyzer(sandbox),
        )
        suite_runner = PytestRunner(
            sandbox,
            timeout_seconds=settings.sandbox_test_timeout_seconds,
        )
        validation = ValidatePullRequest(
            github,
            workspaces,
            analyzers,
            suite_runner,
            max_files=settings.sandbox_max_analyzed_files,
        )

    publisher = PublishFix(github)

    fix_engine = FixEngine(
        workspaces=workspaces,
        files=WorkspaceFiles(),
        fixer=FixerAgent(llm),
        analyzers=analyzers,
        suite_runner=suite_runner,
        settings=FixSettings(
            max_attempts=settings.fix_max_attempts,
            max_changed_lines=settings.fix_max_changed_lines,
            max_file_chars=settings.fix_max_file_chars,
            run_tests=settings.fix_run_tests,
        ),
    )

    checkpointer_manager = build_checkpointer(settings)
    db_manager = build_database_manager(settings)
    run_repository = build_review_run_repository(settings, db_manager)
    telemetry = build_telemetry(settings)

    graph = build_analysis_graph(
        WorkflowDeps(
            github=github,
            llm=llm,
            chunk_chars=settings.review_chunk_chars,
            max_chunks=settings.review_max_chunks,
            workspaces=workspaces,
            analyzers=analyzers,
            max_analyzed_files=settings.sandbox_max_analyzed_files,
            fix_engine=fix_engine,
            fix_min_severity=settings.fix_min_severity,
            fix_max_files=settings.fix_max_files,
            publisher=publisher,
        ),
        checkpointer=checkpointer_manager.checkpointer,
    )
    analysis = AnalyzePullRequest(graph)
    dispatcher = AsyncioRunDispatcher(analysis, run_repository, github, telemetry=telemetry)
    handle_pr_event = HandlePullRequestEvent(
        cache,
        dispatcher,
        bot_login=settings.github_bot_login,
        dedup_ttl_seconds=settings.cache_ttl_seconds,
    )

    repo_monitor = RepoMonitorService(
        github=github,
        cache=cache,
        handle_pr_event=handle_pr_event,
        poll_interval_seconds=45,
    )

    return Container(
        cache=cache,
        github=github,
        handle_pr_event=handle_pr_event,
        analysis=analysis,
        token_tracker=tracker,
        checkpointer_manager=checkpointer_manager,
        approve_run=ApproveRun(graph),
        get_run_status=GetRunStatus(graph),
        run_repository=run_repository,
        telemetry=telemetry,
        _dynamic_sessions=dynamic_sessions,
        db_manager=db_manager,
        graph=graph,
        validation=validation,
        publisher=publisher,
        repo_monitor=repo_monitor,
    )
