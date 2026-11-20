import operator
from typing import Annotated, TypedDict

from app.application.workflow.diff_chunks import RenderedFile
from app.domain.entities.finding import Finding
from app.domain.entities.fix_plan import FixPlan
from app.domain.entities.fix_proposal import FixProposal
from app.domain.entities.impact_report import ImpactReport
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.risk_report import RiskReport
from app.domain.enums import ApprovalDecision


class ReviewState(TypedDict, total=False):
    run_id: str
    repo_full_name: str
    pr_number: int
    pr: PullRequest
    chunks: list[tuple[RenderedFile, ...]]
    findings: Annotated[list[Finding], operator.add]  # reducer: parallel branches append
    notes: Annotated[list[str], operator.add]  # partial failures and skipped files
    impact: ImpactReport
    final_findings: list[Finding]
    risk: RiskReport
    fix_requested: bool
    fix_plan: FixPlan
    proposal: FixProposal
    approval_decision: ApprovalDecision
    approval_feedback: str
    published_branch: str
    published_pr_url: str


class ChunkTask(TypedDict):
    """Payload sent to `analyze_chunk` through the Send API."""

    agent: str
    pr: PullRequest
    chunk: tuple[RenderedFile, ...]


class ImpactTask(TypedDict):
    pr: PullRequest
    chunk: tuple[RenderedFile, ...]


class StaticTask(TypedDict):
    """Payload sent to static analysis through the Send API."""

    pr: PullRequest
