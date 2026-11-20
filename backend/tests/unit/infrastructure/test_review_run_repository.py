from datetime import UTC, datetime

from app.core.config import Settings
from app.domain.entities.finding import Finding
from app.domain.entities.fix_plan import FixAction, FixPlan
from app.domain.entities.review_run import ReviewRun
from app.domain.entities.risk_report import RiskFactor, RiskReport
from app.domain.enums import ApprovalDecision, FindingCategory, RiskLevel, RunStatus, Severity
from app.infrastructure.persistence.database import normalize_database_url
from app.infrastructure.persistence.models import ReviewRunModel
from app.infrastructure.persistence.repositories import (
    InMemoryReviewRunRepository,
    _dict_to_finding,
    _dict_to_fix_plan,
    _dict_to_risk,
    _finding_to_dict,
    _fix_plan_to_dict,
    _model_to_entity,
    _risk_to_dict,
    build_review_run_repository,
)


def _make_run(
    run_id: str = "run-1",
    repo: str = "org/repo",
    pr_num: int = 1,
    status: RunStatus = RunStatus.PENDING,
) -> ReviewRun:
    finding = Finding(
        category=FindingCategory.BUG,
        severity=Severity.HIGH,
        title="Null check missing",
        description="Possible null pointer",
        source="reviewer",
        file_path="src/main.py",
        line_start=10,
        line_end=12,
        suggestion="Add if check",
    )
    risk = RiskReport(
        score=45,
        level=RiskLevel.MEDIUM,
        factors=(RiskFactor("size", 20, "200 lines"),),
    )
    plan = FixPlan(
        actions=(FixAction("src/main.py", "Fix check", (finding.id,)),),
        rationale="1 file to fix",
        attempt=1,
    )
    return ReviewRun(
        id=run_id,
        repo_full_name=repo,
        pr_number=pr_num,
        head_sha="sha123",
        status=status,
        findings=[finding],
        risk=risk,
        fix_plan=plan,
        retry_count=1,
        max_retries=3,
        failure_history=["pytest failed attempt 1"],
        approval=ApprovalDecision.APPROVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_in_memory_repository_save_and_get() -> None:
    repo = InMemoryReviewRunRepository()
    run = _make_run("test-run-1")

    await repo.save(run)
    fetched = await repo.get_by_id("test-run-1")

    assert fetched is not None
    assert fetched.id == "test-run-1"
    assert fetched.repo_full_name == "org/repo"
    assert fetched.status == RunStatus.PENDING
    assert len(fetched.findings) == 1
    assert fetched.findings[0].title == "Null check missing"
    assert fetched.risk is not None
    assert fetched.risk.score == 45
    assert fetched.fix_plan is not None
    assert fetched.fix_plan.actions[0].file_path == "src/main.py"
    assert fetched.approval == ApprovalDecision.APPROVE


async def test_in_memory_repository_list_by_repo_and_pr() -> None:
    repo = InMemoryReviewRunRepository()
    run1 = _make_run("run-1", repo="org/repo", pr_num=10)
    run2 = _make_run("run-2", repo="org/repo", pr_num=10)
    run3 = _make_run("run-3", repo="org/other", pr_num=5)

    await repo.save(run1)
    await repo.save(run2)
    await repo.save(run3)

    repo_runs = await repo.list_by_repo("org/repo")
    assert len(repo_runs) == 2
    assert {r.id for r in repo_runs} == {"run-1", "run-2"}

    pr_runs = await repo.list_by_pr("org/repo", 10)
    assert len(pr_runs) == 2

    empty_runs = await repo.list_by_pr("org/repo", 999)
    assert len(empty_runs) == 0


async def test_in_memory_repository_get_nonexistent_returns_none() -> None:
    repo = InMemoryReviewRunRepository()
    assert await repo.get_by_id("non-existent") is None


def test_serialization_roundtrip_finding() -> None:
    original = Finding(
        category=FindingCategory.SECURITY,
        severity=Severity.CRITICAL,
        title="SQL injection",
        description="Untrusted user input",
        source="security",
        file_path="app/db.py",
        line_start=42,
        line_end=45,
        suggestion="Use parameters",
    )
    d = _finding_to_dict(original)
    restored = _dict_to_finding(d)

    assert restored.id == original.id
    assert restored.category == original.category
    assert restored.severity == original.severity
    assert restored.title == original.title
    assert restored.file_path == original.file_path
    assert restored.line_start == original.line_start
    assert restored.suggestion == original.suggestion


def test_serialization_roundtrip_risk() -> None:
    original = RiskReport(
        score=75,
        level=RiskLevel.HIGH,
        factors=(
            RiskFactor("sensitive_files", 20, "3 files"),
            RiskFactor("size", 20, "500 lines"),
        ),
    )
    d = _risk_to_dict(original)
    restored = _dict_to_risk(d)

    assert restored is not None
    assert restored.score == 75
    assert restored.level == RiskLevel.HIGH
    assert len(restored.factors) == 2
    assert restored.factors[0].name == "sensitive_files"


def test_serialization_roundtrip_fix_plan() -> None:
    original = FixPlan(
        actions=(FixAction("a.py", "fix a", ("f1", "f2")),),
        rationale="1 file",
        attempt=2,
    )
    d = _fix_plan_to_dict(original)
    restored = _dict_to_fix_plan(d)

    assert restored is not None
    assert restored.attempt == 2
    assert restored.actions[0].finding_ids == ("f1", "f2")


def test_model_to_entity_conversion() -> None:
    now = datetime.now(UTC)
    model = ReviewRunModel(
        id="run-m1",
        repo_full_name="org/repo",
        pr_number=5,
        head_sha="sha999",
        status=RunStatus.AWAITING_APPROVAL.value,
        retry_count=0,
        max_retries=3,
        approval=None,
        findings_data=[],
        risk_data=None,
        fix_plan_data=None,
        failure_history=[],
        created_at=now,
        updated_at=now,
    )
    entity = _model_to_entity(model)
    assert entity.id == "run-m1"
    assert entity.status == RunStatus.AWAITING_APPROVAL
    assert entity.approval is None


def test_normalize_database_url() -> None:
    assert (
        normalize_database_url("postgresql://user:pass@host:5432/db")
        == "postgresql+psycopg://user:pass@host:5432/db"
    )
    assert (
        normalize_database_url("postgres://user:pass@host:5432/db")
        == "postgresql+psycopg://user:pass@host:5432/db"
    )
    assert normalize_database_url("sqlite+aiosqlite:///test.db") == "sqlite+aiosqlite:///test.db"


def test_build_review_run_repository_fallback() -> None:
    settings = Settings(checkpointer_backend="memory")
    repo = build_review_run_repository(settings, None)
    assert isinstance(repo, InMemoryReviewRunRepository)
