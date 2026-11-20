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


@router.post("/{run_id}/approve")
async def approve(
    run_id: str,
    body: ApprovalRequest,
    use_case: ApproveRunDep,
) -> dict[str, Any]:
    try:
        result = await use_case.execute(
            run_id=run_id,
            decision=body.decision,
            feedback=body.feedback,
        )
    except RunNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except RunNotAwaitingApprovalError as exc:
        raise ConflictError(str(exc)) from exc

    return asdict(result)
