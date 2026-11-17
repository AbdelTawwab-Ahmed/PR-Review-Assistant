from typing import Any

from app.application.workflow.state import ReviewState
from app.domain.services.finding_merge import merge_findings


async def aggregate_findings(state: ReviewState) -> dict[str, Any]:
    return {"final_findings": merge_findings(state.get("findings", []))}