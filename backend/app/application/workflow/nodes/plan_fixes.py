from typing import Any

from app.application.workflow.state import ReviewState
from app.domain.enums import Severity
from app.domain.services.fix_planning import plan_fixes as build_fix_plan


def make_plan_fixes(min_severity: Severity, max_files: int):
    async def plan_fixes(state: ReviewState) -> dict[str, Any]:
        plan = build_fix_plan(
            state["final_findings"],
            state["pr"].files,
            min_severity=min_severity,
            max_files=max_files,
        )
        return {"fix_plan": plan}

    return plan_fixes
