from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command

from app.application.ports.repositories import ReviewRunRepository
from app.domain.enums import ApprovalDecision, FixStatus, RunStatus
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
    def __init__(
        self,
        graph: Any,
        repository: ReviewRunRepository | None = None,
    ) -> None:
        self._graph = graph
        self._repository = repository

    async def execute(
        self,
        run_id: str,
        decision: ApprovalDecision,
        feedback: str = "",
    ) -> ApproveResult:
        config = {"configurable": {"thread_id": run_id}}

        state_snapshot = await self._graph.aget_state(config)
        if not state_snapshot or not state_snapshot.values:
            run = await self._repository.get_by_id(run_id) if self._repository else None
            if run is not None and run.status == RunStatus.AWAITING_PLAN_APPROVAL:
                if decision == ApprovalDecision.REJECT:
                    run.status = RunStatus.REJECTED
                    run.approval = decision
                    run.updated_at = datetime.now(UTC)
                    if self._repository:
                        await self._repository.save(run)
                    return ApproveResult(run_id=run_id, decision=decision, status="completed")
                result_state = await self._graph.ainvoke(
                    {
                        "run_id": run_id,
                        "repo_full_name": run.repo_full_name,
                        "pr_number": run.pr_number,
                        "fix_requested": True,
                        "plan_approval_decision": decision,
                        "plan_approval_feedback": feedback,
                    },
                    config=config,
                )
            else:
                raise RunNotFoundError(f"Run {run_id} not found")
        else:
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

        proposal = result_state.get("proposal")
        notes = list(result_state.get("notes", ()))
        if proposal and getattr(proposal, "notes", None):
            for note in proposal.notes:
                if note not in notes:
                    notes.append(note)

        if self._repository is not None:
            run = await self._repository.get_by_id(run_id)
            if run is not None:
                if result_state.get("final_findings"):
                    run.findings = list(result_state["final_findings"])
                if result_state.get("fix_plan") is not None:
                    run.fix_plan = result_state["fix_plan"]
                for note in notes:
                    if note not in run.failure_history:
                        run.failure_history.append(note)
                publish_failed = any(
                    note.startswith(
                        (
                            "GitHub write permission denied",
                            "Failed to publish fix",
                            "Unexpected error publishing fix",
                        )
                    )
                    for note in notes
                )
                if result_state.get("__interrupt__"):
                    run.status = RunStatus.AWAITING_APPROVAL
                elif result_state.get("published_pr_url"):
                    run.status = RunStatus.READY_TO_MERGE
                    run.approval = decision
                elif decision == ApprovalDecision.REJECT:
                    run.status = RunStatus.REJECTED
                    run.approval = decision
                elif publish_failed or (proposal and proposal.status == FixStatus.FAILED):
                    run.status = RunStatus.FAILED
                else:
                    run.status = RunStatus.READY_TO_MERGE
                run.updated_at = datetime.now(UTC)
                await self._repository.save(run)

        return ApproveResult(
            run_id=run_id,
            decision=decision,
            status="completed" if not result_state.get("__interrupt__") else "interrupted",
            published_branch=result_state.get("published_branch"),
            published_pr_url=result_state.get("published_pr_url"),
            notes=tuple(notes),
        )
