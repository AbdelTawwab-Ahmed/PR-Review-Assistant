
import operator
from typing import Annotated, TypedDict

from app.application.workflow.diff_chunks import RenderedFile
from app.domain.entities.finding import Finding
from app.domain.entities.impact_report import ImpactReport
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.risk_report import RiskReport


class ReviewState(TypedDict, total=False):
    repo_full_name: str
    pr_number: int
    pr: PullRequest
    chunks: list[tuple[RenderedFile, ...]]
    findings: Annotated[list[Finding], operator.add]  # reducer: parallel branches append
    notes: Annotated[list[str], operator.add]  # partial failures and skipped files
    impact: ImpactReport
    final_findings: list[Finding]
    risk: RiskReport


class ChunkTask(TypedDict):
    """Payload sent to `analyze_chunk` through the Send API."""

    agent: str
    pr: PullRequest
    chunk: tuple[RenderedFile, ...]


class ImpactTask(TypedDict):
    pr: PullRequest
    chunk: tuple[RenderedFile, ...]


class StaticTask(TypedDict):
    pr: PullRequest
