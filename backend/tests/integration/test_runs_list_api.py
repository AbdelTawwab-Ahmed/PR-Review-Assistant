from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.domain.entities.review_run import ReviewRun
from app.domain.enums import RunStatus
from app.infrastructure.persistence.repositories import InMemoryReviewRunRepository
from app.interfaces.api.deps import get_run_repository
from app.main import create_app


def _make_test_run(run_id: str, repo: str = "org/repo", pr_num: int = 1) -> ReviewRun:
    now = datetime.now(UTC)
    return ReviewRun(
        id=run_id,
        repo_full_name=repo,
        pr_number=pr_num,
        head_sha="sha123",
        status=RunStatus.PENDING,
        created_at=now,
        updated_at=now,
    )


async def test_list_runs_empty() -> None:
    app = create_app()
    repo = InMemoryReviewRunRepository()
    app.dependency_overrides[get_run_repository] = lambda: repo

    response = TestClient(app).get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_runs_by_repo_and_pr() -> None:
    app = create_app()
    repo = InMemoryReviewRunRepository()
    await repo.save(_make_test_run("r1", "org/repo", 1))
    await repo.save(_make_test_run("r2", "org/repo", 2))
    await repo.save(_make_test_run("r3", "other/repo", 1))
    app.dependency_overrides[get_run_repository] = lambda: repo

    client = TestClient(app)

    # Filter by repo
    res_repo = client.get("/api/runs?repo_full_name=org/repo")
    assert res_repo.status_code == 200
    data = res_repo.json()
    assert len(data) == 2
    assert {r["id"] for r in data} == {"r1", "r2"}

    # Filter by repo + PR
    res_pr = client.get("/api/runs?repo_full_name=org/repo&pr_number=1")
    assert res_pr.status_code == 200
    data_pr = res_pr.json()
    assert len(data_pr) == 1
    assert data_pr[0]["id"] == "r1"
