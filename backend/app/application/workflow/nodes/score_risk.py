from typing import Any

from app.application.workflow.state import ReviewState
from app.domain.services.risk_scoring import compute_risk


async def score_risk(state: ReviewState) -> dict[str, Any]:
    return {"risk": compute_risk(state["pr"], state["final_findings"])}
