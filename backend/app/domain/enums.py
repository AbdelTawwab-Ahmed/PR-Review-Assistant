
from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_LEVEL = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class FixStatus(StrEnum):
    NOTHING_TO_FIX = "nothing_to_fix"
    FAILED = "failed"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


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
