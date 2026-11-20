from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from app.core.errors import NotFoundError
from app.domain.exceptions import RunNotFoundError
from app.interfaces.api.deps import GetRunStatusDep, RunRepoDep

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
async def list_runs(
    repository: RunRepoDep,
    repo_full_name: str | None = None,
    pr_number: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if repo_full_name and pr_number is not None:
        runs = await repository.list_by_pr(repo_full_name, pr_number, limit=limit)
    elif repo_full_name:
        runs = await repository.list_by_repo(repo_full_name, limit=limit)
    else:
        runs = []
    return [asdict(r) for r in runs]


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    use_case: GetRunStatusDep,
) -> dict[str, Any]:
    try:
        result = await use_case.execute(run_id)
    except RunNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return asdict(result)
