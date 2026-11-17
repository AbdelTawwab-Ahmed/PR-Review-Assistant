from typing import Any

from app.application.workflow.diff_chunks import build_chunks
from app.application.workflow.state import ReviewState


def make_plan_analysis(chunk_chars: int, max_chunks: int):
    async def plan_analysis(state: ReviewState) -> dict[str, Any]:
        plan = build_chunks(state["pr"].files, chunk_chars, max_chunks)
        update: dict[str, Any] = {"chunks": list(plan.chunks)}
        if plan.skipped:
            shown = ", ".join(plan.skipped[:5])
            update["notes"] = [f"{len(plan.skipped)} file(s) not analyzed (size limit): {shown}"]
        return update

    return plan_analysis