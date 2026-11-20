from fastapi.testclient import TestClient

from app.application.use_cases.approve_run import ApproveResult
from app.application.use_cases.get_run_status import RunStatusResult
from app.domain.entities.risk_report import RiskReport
from app.domain.enums import ApprovalDecision, RiskLevel, RunStatus
from app.domain.exceptions import RunNotAwaitingApprovalError, RunNotFoundError
from app.interfaces.api.deps import get_approve_run, get_run_status
from app.main import create_app


class FakeApproveRun:
    def __init__(
        self, result: ApproveResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple] = []

    async def execute(
        self, run_id: str, decision: ApprovalDecision, feedback: str = ""
    ) -> ApproveResult:
        self.calls.append((run_id, decision, feedback))
        if self.error:
            raise self.error
        return self.result or ApproveResult(
            run_id=run_id,
            decision=decision,
            status="completed",
            published_branch="prra/fix-pr1-abc1234",
            published_pr_url="https://github.com/org/repo/pull/10",
        )


class FakeGetRunStatus:
    def __init__(
        self, result: RunStatusResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error

    async def execute(self, run_id: str) -> RunStatusResult:
        if self.error:
            raise self.error
        return self.result or RunStatusResult(
            run_id=run_id,
            status=RunStatus.AWAITING_APPROVAL,
            repo_full_name="org/repo",
            pr_number=1,
            head_sha="abc1234",
            findings_count=2,
            risk=RiskReport(score=40, level=RiskLevel.MEDIUM),
            proposal=None,
            approval_decision=None,
            published_branch=None,
            published_pr_url=None,
            notes=(),
        )


def test_get_run_success() -> None:
    app = create_app()
    app.dependency_overrides[get_run_status] = lambda: FakeGetRunStatus()

    response = TestClient(app).get("/api/runs/run-123")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run-123"
    assert data["status"] == "awaiting_approval"
    assert data["repo_full_name"] == "org/repo"


def test_get_run_not_found() -> None:
    app = create_app()
    app.dependency_overrides[get_run_status] = lambda: FakeGetRunStatus(
        error=RunNotFoundError("Run not found")
    )

    response = TestClient(app).get("/api/runs/unknown-run")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_approve_run_success() -> None:
    app = create_app()
    fake_approve = FakeApproveRun()
    app.dependency_overrides[get_approve_run] = lambda: fake_approve

    response = TestClient(app).post(
        "/api/runs/run-123/approve",
        json={"decision": "approve", "feedback": "looks great"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run-123"
    assert data["decision"] == "approve"
    assert data["status"] == "completed"
    assert data["published_branch"] == "prra/fix-pr1-abc1234"
    assert fake_approve.calls[0] == ("run-123", ApprovalDecision.APPROVE, "looks great")


def test_approve_run_not_found() -> None:
    app = create_app()
    app.dependency_overrides[get_approve_run] = lambda: FakeApproveRun(
        error=RunNotFoundError("Run not found")
    )

    response = TestClient(app).post(
        "/api/runs/missing/approve",
        json={"decision": "approve"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_approve_run_conflict_when_not_awaiting() -> None:
    app = create_app()
    app.dependency_overrides[get_approve_run] = lambda: FakeApproveRun(
        error=RunNotAwaitingApprovalError("Not awaiting approval")
    )

    response = TestClient(app).post(
        "/api/runs/already-approved/approve",
        json={"decision": "approve"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
