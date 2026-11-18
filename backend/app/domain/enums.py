from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(StrEnum):
    BUG = "bug"
    SECURITY = "security"
    CODE_SMELL = "code_smell"
    DESIGN = "design"
    STYLE = "style"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RunStatus(StrEnum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    FIXING = "fixing"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    UPDATING_PR = "updating_pr"
    READY_TO_MERGE = "ready_to_merge"
    REJECTED = "rejected"
    FAILED = "failed"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


class FixStatus(StrEnum):
    VERIFIED = "verified"  # checks ran and nothing got worse
    UNVERIFIED = "unverified"  # edits exist but no sandbox tools were available
    FAILED = "failed"  # still regressing after the last attempt, no changes proposed
    NOTHING_TO_FIX = "nothing_to_fix"


SEVERITY_LEVEL: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}