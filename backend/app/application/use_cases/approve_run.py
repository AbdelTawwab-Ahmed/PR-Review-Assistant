from dataclasses import dataclass
from typing import Any

from langgraph.types import Command

from app.domain.enums import ApprovalDecision
from app.domain.exceptions import RunNotAwaitingApprovalError, RunNotFoundError


@dataclass(frozen=True)
class ApproveResult:
    run_id: str
    decision: ApprovalDecision
    status: str
    published_branch: str | None = None
    published_pr_url: str | None = None
    notes: tuple[str, ...] = ()


class ApproveRun:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    async def execute(
        self,
        run_id: str,
        decision: ApprovalDecision,
        feedback: str = "",
    ) -> ApproveResult:
        config = {"configurable": {"thread_id": run_id}}

        state_snapshot = await self._graph.aget_state(config)
        if not state_snapshot or not state_snapshot.values:
            raise RunNotFoundError(f"Run {run_id} not found")

        # Check if graph has any pending interrupts
        has_interrupts = any(t.interrupts for t in state_snapshot.tasks)
        if not has_interrupts and not state_snapshot.next:
            raise RunNotAwaitingApprovalError(f"Run {run_id} is not awaiting approval")

        resume_payload = {
            "decision": decision.value,
            "feedback": feedback,
        }
        result_state = await self._graph.ainvoke(
            Command(resume=resume_payload),
            config=config,
        )

        return ApproveResult(
            run_id=run_id,
            decision=decision,
            status="completed" if not result_state.get("__interrupt__") else "interrupted",
            published_branch=result_state.get("published_branch"),
            published_pr_url=result_state.get("published_pr_url"),
            notes=tuple(result_state.get("notes", ())),
        )
