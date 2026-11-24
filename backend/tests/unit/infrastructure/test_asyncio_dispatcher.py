from unittest.mock import AsyncMock

from app.application.events import PullRequestEvent
from app.application.use_cases.analyze_pull_request import AnalysisResult
from app.domain.entities.risk_report import RiskReport
from app.domain.enums import RiskLevel, RunStatus
from app.infrastructure.dispatch.asyncio_dispatcher import AsyncioRunDispatcher
from app.infrastructure.persistence.repositories import InMemoryReviewRunRepository


def _event() -> PullRequestEvent:
    return PullRequestEvent(
        delivery_id="d1",
        action="synchronize",
        repo_full_name="org/repo",
        number=1,
        head_sha="abcdef1234567",
        base_branch="main",
        head_branch="feature/x",
        title="Test PR",
        author="dev",
        sender="dev",
    )


async def test_dispatcher_marks_run_failed_when_llm_analysis_fails() -> None:
    analysis = AsyncMock()
    analysis.execute.return_value = AnalysisResult(
        repo_full_name="org/repo",
        pr_number=1,
        head_sha="abcdef1234567",
        findings=(),
        risk=RiskReport(score=0, level=RiskLevel.LOW, factors=()),
        impact=None,
        notes=("reviewer could not analyze 1 file(s): AuthenticationError",),
    )
    repo = InMemoryReviewRunRepository()
    github = AsyncMock()
    dispatcher = AsyncioRunDispatcher(analysis, repo, github)

    await dispatcher._process_pr(_event())

    saved = await repo.get_by_id("org/repo#1#abcdef1")
    assert saved is not None
    assert saved.status == RunStatus.FAILED
    assert any("AuthenticationError" in msg for msg in saved.failure_history)
    github._post_json.assert_not_called()


async def test_dispatcher_marks_clean_run_ready_to_merge() -> None:
    analysis = AsyncMock()
    analysis.execute.return_value = AnalysisResult(
        repo_full_name="org/repo",
        pr_number=1,
        head_sha="abcdef1234567",
        findings=(),
        risk=RiskReport(score=0, level=RiskLevel.LOW, factors=()),
        impact=None,
        notes=(),
    )
    repo = InMemoryReviewRunRepository()
    github = AsyncMock()
    dispatcher = AsyncioRunDispatcher(analysis, repo, github)

    await dispatcher._process_pr(_event())

    saved = await repo.get_by_id("org/repo#1#abcdef1")
    assert saved is not None
    assert saved.status == RunStatus.READY_TO_MERGE
