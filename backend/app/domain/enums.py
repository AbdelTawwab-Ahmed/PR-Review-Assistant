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
