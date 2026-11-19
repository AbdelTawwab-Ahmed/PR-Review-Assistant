from dataclasses import dataclass
from typing import Any

from app.domain.entities.finding import Finding
from app.domain.entities.fix_proposal import FixProposal
from app.domain.entities.impact_report import ImpactReport
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.risk_report import RiskReport
from app.domain.enums import FixStatus


@dataclass(frozen=True)
class AnalysisResult:
    repo_full_name: str
    pr_number: int
    head_sha: str
    findings: tuple[Finding, ...]
    risk: RiskReport
    impact: ImpactReport | None
    notes: tuple[str, ...]
    fix_proposal: FixProposal | None = None


class AnalyzePullRequest:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    async def execute(
        self,
        repo_full_name: str,
        pr_number: int,
        *,
        propose_fixes: bool = False,
    ) -> AnalysisResult:
        state = await self._graph.ainvoke(
            {
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "fix_requested": propose_fixes,
            }
        )

        pr: PullRequest = state["pr"]
        proposal = state.get("proposal")

        if propose_fixes and proposal is None:
            proposal = FixProposal(
                FixStatus.NOTHING_TO_FIX,
                pr.head_sha,
                summary="No findings qualify for automatic fixing.",
            )

        return AnalysisResult(
            repo_full_name=pr.repo_full_name,
            pr_number=pr.number,
            head_sha=pr.head_sha,
            findings=tuple(state.get("final_findings", [])),
            risk=state["risk"],
            impact=state.get("impact"),
            notes=tuple(state.get("notes", [])),
            fix_proposal=proposal,
        )
