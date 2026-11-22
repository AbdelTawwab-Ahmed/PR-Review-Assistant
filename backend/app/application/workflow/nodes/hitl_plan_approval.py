import logging
from typing import Any

from langgraph.types import interrupt

from app.application.workflow.state import ReviewState
from app.domain.enums import ApprovalDecision

logger = logging.getLogger(__name__)


def make_hitl_plan_approval():
    """Stage 1 Human-in-the-Loop Gate: Requires human approval before remediation agents run."""

    async def hitl_plan_approval(state: ReviewState) -> dict[str, Any]:
        findings = state.get("final_findings", [])
        risk = state.get("risk")

        interrupt_payload = {
            "stage": "initial_approval",
            "status": "awaiting_plan_approval",
            "repo_full_name": state.get("repo_full_name"),
            "pr_number": state.get("pr_number"),
            "findings_count": len(findings),
            "findings": [
                {
                    "id": f.id,
                    "category": f.category.value
                    if hasattr(f.category, "value")
                    else str(f.category),
                    "severity": f.severity.value
                    if hasattr(f.severity, "value")
                    else str(f.severity),
                    "title": f.title,
                    "description": f.description,
                    "file_path": f.file_path,
                    "line_start": f.line_start,
                    "line_end": f.line_end,
                    "suggestion": f.suggestion,
                }
                for f in findings
            ],
            "risk_score": risk.score if risk else 0,
            "risk_level": risk.level.value if risk and hasattr(risk.level, "value") else "low",
            "proposed_remediation_summary": (
                f"Identified {len(findings)} issue(s) across codebase. "
                "Awaiting human approval to initialize remediation agents."
            ),
        }

        # Pauses workflow until resumed by human reviewer
        logger.info(
            "Pausing at Stage 1 HITL: Initial Remediation Authorization for %s",
            state.get("repo_full_name"),
        )
        decision_data = interrupt(interrupt_payload)
        logger.info("Stage 1 HITL resumed with decision: %s", decision_data)

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
            "plan_approval_decision": decision,
            "plan_approval_feedback": feedback,
        }

    return hitl_plan_approval
