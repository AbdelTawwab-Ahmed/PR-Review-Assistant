from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.finding import Finding
from app.domain.entities.fix_plan import FixPlan
from app.domain.entities.risk_report import RiskReport
from app.domain.enums import ApprovalDecision, RunStatus
from app.domain.exceptions import InvalidApprovalError, InvalidTransitionError

S = RunStatus

ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    S.PENDING: frozenset({S.ANALYZING, S.FAILED}),
    S.ANALYZING: frozenset({S.PLANNING, S.FAILED}),
    S.PLANNING: frozenset({S.FIXING, S.UPDATING_PR, S.FAILED}),
    S.FIXING: frozenset({S.VALIDATING, S.FAILED}),
    S.VALIDATING: frozenset({S.AWAITING_APPROVAL, S.PLANNING, S.FAILED}),
    S.AWAITING_APPROVAL: frozenset({S.UPDATING_PR, S.PLANNING, S.REJECTED}),
    S.UPDATING_PR: frozenset({S.READY_TO_MERGE, S.FAILED}),
    S.READY_TO_MERGE: frozenset(),
    S.REJECTED: frozenset(),
    S.FAILED: frozenset(),
}

_APPROVAL_TARGETS: dict[ApprovalDecision, RunStatus] = {
    ApprovalDecision.APPROVE: S.UPDATING_PR,
    ApprovalDecision.REJECT: S.REJECTED,
    ApprovalDecision.REQUEST_CHANGES: S.PLANNING,
}


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ReviewRun:
    repo_full_name: str
    pr_number: int
    head_sha: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: RunStatus = RunStatus.PENDING
    findings: list[Finding] = field(default_factory=list)
    risk: RiskReport | None = None
    fix_plan: FixPlan | None = None
    retry_count: int = 0
    max_retries: int = 3
    failure_history: list[str] = field(default_factory=list)
    approval: ApprovalDecision | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def is_terminal(self) -> bool:
        return not ALLOWED_TRANSITIONS[self.status]

    def transition_to(self, new_status: RunStatus) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransitionError(f"Cannot move from {self.status} to {new_status}")
        self.status = new_status
        self.updated_at = _now()

    def add_findings(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)
        self.updated_at = _now()

    def register_validation_failure(self, reason: str) -> None:
        """Record a failed validation; retry via PLANNING, or fail when retries are exhausted."""
        self.failure_history.append(reason)
        self.retry_count += 1
        if self.retry_count <= self.max_retries:
            self.transition_to(RunStatus.PLANNING)
        else:
            self.transition_to(RunStatus.FAILED)

    def apply_approval(self, decision: ApprovalDecision) -> None:
        if self.status is not RunStatus.AWAITING_APPROVAL:
            raise InvalidApprovalError("Run is not awaiting approval")
        self.approval = decision
        self.transition_to(_APPROVAL_TARGETS[decision])
