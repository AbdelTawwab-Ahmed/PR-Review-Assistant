from dataclasses import asdict
import logging
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.application.events import PullRequestEvent
from app.application.use_cases.handle_pr_event import EventOutcome
from app.core.container import Container
from app.core.errors import NotFoundError
from app.domain.exceptions import RunNotFoundError
from app.infrastructure.persistence.repositories import (
    _finding_to_dict,
    _fix_plan_to_dict,
    _risk_to_dict,
    review_run_to_dict,
)
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
        delivery_id=f"manual-{pr_info.head_sha[:7]}-{uuid.uuid4().hex[:8]}",
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
    if outcome == EventOutcome.DUPLICATE:
        await container.handle_pr_event._dispatcher.dispatch(event)
        outcome = EventOutcome.ACCEPTED

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
    repository: RunRepoDep,
) -> dict[str, Any]:
    # 1. Check LangGraph state
    try:
        result = await use_case.execute(run_id)
        result_dict = jsonable_encoder(asdict(result))
        if "findings" not in result_dict or not result_dict["findings"]:
            run = await repository.get_by_id(run_id)
            if run and run.findings:
                result_dict["findings"] = [_finding_to_dict(f) if hasattr(f, "category") else f for f in run.findings]
        return result_dict
    except RunNotFoundError:
        pass

    # 2. Check Repository entity fallback (useful while graph is actively running or if checkpointer restarted)
    run = await repository.get_by_id(run_id)
    if run is not None:
        return jsonable_encoder(
            {
                "run_id": run.id,
                "status": run.status.value,
                "repo_full_name": run.repo_full_name,
                "pr_number": run.pr_number,
                "head_sha": run.head_sha,
                "findings_count": len(run.findings),
                "findings": [_finding_to_dict(f) if hasattr(f, "category") else f for f in run.findings],
                "risk": _risk_to_dict(run.risk) if hasattr(run.risk, "level") else run.risk,
                "proposal": _fix_plan_to_dict(run.fix_plan) if hasattr(run.fix_plan, "actions") else run.fix_plan,
                "approval_decision": run.approval.value if run.approval and hasattr(run.approval, "value") else None,
                "published_branch": None,
                "published_pr_url": None,
                "notes": tuple(run.failure_history or ()),
                "interrupt_payload": None,
            }
        )

    raise NotFoundError(f"Run {run_id} not found")
