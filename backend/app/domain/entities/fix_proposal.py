from dataclasses import dataclass

from app.domain.enums import FixStatus


@dataclass(frozen=True)
class FileChange:
    path: str
    old_content: str
    new_content: str


@dataclass(frozen=True)
class FixProposal:
    status: FixStatus
    base_sha: str = ""
    changes: tuple[FileChange, ...] = ()
    attempts: int = 0
    targeted_finding_ids: tuple[str, ...] = ()
    summary: str = ""
    notes: tuple[str, ...] = ()

    @property
    def publishable(self) -> bool:
        """Only verified proposals with actual changes may be published."""
        return self.status is FixStatus.VERIFIED and bool(self.changes)
