from dataclasses import dataclass
from typing import Any

from app.domain.entities.fix_proposal import FixProposal
from app.domain.entities.risk_report import RiskReport
from app.domain.enums import ApprovalDecision, RunStatus
from app.domain.exceptions import RunNotFoundError


@dataclass(frozen=True)
class RunStatusResult:
    run_id: str
    status: RunStatus
    repo_full_name: str
    pr_number: int
    head_sha: str
    findings_count: int
    risk: RiskReport | None
    proposal: FixProposal | None
    approval_decision: ApprovalDecision | None
    published_branch: str | None
    published_pr_url: str | None
    notes: tuple[str, ...]
    interrupt_payload: dict[str, Any] | None = None


class GetRunStatus:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    async def execute(self, run_id: str) -> RunStatusResult:
        config = {"configurable": {"thread_id": run_id}}
        state_snapshot = await self._graph.aget_state(config)
        if not state_snapshot or not state_snapshot.values:
            raise RunNotFoundError(f"Run {run_id} not found")

        values = state_snapshot.values
        interrupts = [i.value for t in state_snapshot.tasks for i in t.interrupts]
        interrupt_payload = interrupts[0] if interrupts else None

        if interrupt_payload or (state_snapshot.next and ("hitl_approval" in state_snapshot.next or "hitl_plan_approval" in state_snapshot.next)):
            if interrupt_payload and interrupt_payload.get("status") == "awaiting_plan_approval":
                status = RunStatus.AWAITING_PLAN_APPROVAL
            elif state_snapshot.next and "hitl_plan_approval" in state_snapshot.next:
                status = RunStatus.AWAITING_PLAN_APPROVAL
            else:
                status = RunStatus.AWAITING_APPROVAL
        elif values.get("published_pr_url"):
            status = RunStatus.READY_TO_MERGE
        elif values.get("approval_decision") == ApprovalDecision.REJECT or values.get("plan_approval_decision") == ApprovalDecision.REJECT:
            status = RunStatus.REJECTED
        elif values.get("proposal"):
            status = RunStatus.VALIDATING
        elif values.get("fix_plan"):
            status = RunStatus.FIXING
        elif values.get("risk") and not values.get("final_findings"):
            status = RunStatus.READY_TO_MERGE
        else:
            status = RunStatus.ANALYZING

        pr = values.get("pr")

        return RunStatusResult(
            run_id=run_id,
            status=status,
            repo_full_name=values.get("repo_full_name", ""),
            pr_number=values.get("pr_number", 0),
            head_sha=pr.head_sha if pr else "",
            findings_count=len(values.get("final_findings", [])),
            risk=values.get("risk"),
            proposal=values.get("proposal"),
            approval_decision=values.get("approval_decision"),
            published_branch=values.get("published_branch"),
            published_pr_url=values.get("published_pr_url"),
            notes=tuple(values.get("notes", ())),
            interrupt_payload=interrupt_payload,
        )
