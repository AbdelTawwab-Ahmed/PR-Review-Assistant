from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import ConflictError, NotFoundError
from app.domain.enums import ApprovalDecision
from app.domain.exceptions import RunNotAwaitingApprovalError, RunNotFoundError
from app.interfaces.api.deps import ApproveRunDep

router = APIRouter(prefix="/runs", tags=["approvals"])


class ApprovalRequest(BaseModel):
    decision: ApprovalDecision
    feedback: str = ""
    run_id: str | None = None


@router.post("/approve")
async def approve_direct(
    body: ApprovalRequest,
    use_case: ApproveRunDep,
    run_id: str | None = None,
) -> dict[str, Any]:
    target_id = run_id or body.run_id
    if not target_id:
        raise NotFoundError("run_id is required")
    try:
        result = await use_case.execute(
            run_id=target_id,
            decision=body.decision,
            feedback=body.feedback,
        )
    except RunNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except RunNotAwaitingApprovalError as exc:
        raise ConflictError(str(exc)) from exc

    return asdict(result)


@router.post("/{run_id:path}/approve")
async def approve(
    run_id: str,
    body: ApprovalRequest,
    use_case: ApproveRunDep,
) -> dict[str, Any]:
    return await approve_direct(body, use_case, run_id=run_id)
