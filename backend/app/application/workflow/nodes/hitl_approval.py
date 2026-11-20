import logging
from typing import Any

from langgraph.types import interrupt

from app.application.workflow.state import ReviewState
from app.domain.enums import ApprovalDecision

logger = logging.getLogger(__name__)


def make_hitl_approval():
    async def hitl_approval(state: ReviewState) -> dict[str, Any]:
        proposal = state.get("proposal")
        risk = state.get("risk")

        summary = proposal.summary if proposal else ""
        changes = proposal.changes if proposal else ()

        interrupt_payload = {
            "status": "awaiting_approval",
            "repo_full_name": state.get("repo_full_name"),
            "pr_number": state.get("pr_number"),
            "proposal_status": proposal.status.value if proposal else None,
            "proposal_summary": summary,
            "changes": [
                {
                    "path": c.path,
                    "old_content": c.old_content,
                    "new_content": c.new_content,
                }
                for c in changes
            ],
            "risk_score": risk.score if risk else None,
            "risk_level": risk.level.value if risk else None,
        }

        # interrupt pauses execution until resumed via Command(resume=...)
        decision_data = interrupt(interrupt_payload)

        logger.info("HITL approval resumed with decision data: %s", decision_data)

        if isinstance(decision_data, str):
            decision = ApprovalDecision(decision_data)
            feedback = ""
        elif isinstance(decision_data, dict):
            decision_val = decision_data.get("decision", ApprovalDecision.REJECT.value)
            decision = ApprovalDecision(decision_val)
            feedback = decision_data.get("feedback", "")
        else:
            decision = ApprovalDecision.REJECT
            feedback = ""

        return {
            "approval_decision": decision,
            "approval_feedback": feedback,
        }

    return hitl_approval
