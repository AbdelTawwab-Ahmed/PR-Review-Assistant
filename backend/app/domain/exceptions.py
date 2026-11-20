class DomainError(Exception):
    """Base class for business-rule violations."""


class InvalidTransitionError(DomainError):
    """Raised when a run moves to a status that is not allowed from its current one."""


class InvalidApprovalError(DomainError):
    """Raised when an approval decision is applied outside the approval stage."""


class RunNotFoundError(DomainError):
    """Raised when a run cannot be found in state."""


class RunNotAwaitingApprovalError(DomainError):
    """Raised when a run is not currently waiting for approval."""
