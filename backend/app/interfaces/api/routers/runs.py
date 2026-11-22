from dataclasses import asdict
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.application.events import PullRequestEvent
from app.core.container import Container
from app.core.errors import NotFoundError
from app.domain.exceptions import RunNotFoundError
from app.infrastructure.persistence.repositories import review_run_to_dict
from app.interfaces.api.deps import GetRunStatusDep, RunRepoDep, get_container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


class TriggerRunRequest(BaseModel):
    repo_full_name: str
    pr_number: int


@router.get("")
async def list_runs(
    repository: RunRepoDep,
    repo_full_name: str | None = None,
    pr_number: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    try:
        if repo_full_name and pr_number is not None:
            runs = await repository.list_by_pr(repo_full_name, pr_number, limit=limit)
        elif repo_full_name:
            runs = await repository.list_by_repo(repo_full_name, limit=limit)
        else:
            runs = await repository.list_all(limit=limit)
        return [review_run_to_dict(r) for r in runs]
    except Exception as exc:
        logger.warning("Error in list_runs: %s", exc)
        return []


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    body: TriggerRunRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    pr_info = await container.github.get_pull_request(body.repo_full_name, body.pr_number)
    event = PullRequestEvent(
        delivery_id=f"manual-{pr_info.head_sha[:7]}",
        action="synchronize",
        repo_full_name=body.repo_full_name,
        number=body.pr_number,
        head_sha=pr_info.head_sha,
        base_branch=pr_info.base_branch,
        head_branch=pr_info.head_branch,
        title=pr_info.title,
        author=pr_info.author,
        sender=pr_info.author,
    )
    outcome = await container.handle_pr_event.execute(event)
    run_id = f"{body.repo_full_name}#{body.pr_number}#{pr_info.head_sha[:7]}"
    return {
        "status": outcome.value,
        "run_id": run_id,
        "repo": body.repo_full_name,
        "pr_number": body.pr_number,
        "head_sha": pr_info.head_sha,
        "dashboard_url": f"/runs/{run_id}",
    }


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    use_case: GetRunStatusDep,
) -> dict[str, Any]:
    try:
        result = await use_case.execute(run_id)
    except RunNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return jsonable_encoder(asdict(result))
