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
    base_sha: str = ""  # the PR head the fixes were generated against
    changes: tuple[FileChange, ...] = ()
    attempts: int = 0
    targeted_finding_ids: tuple[str, ...] = ()
    summary: str = ""
    notes: tuple[str, ...] = ()

    @property
    def publishable(self) -> bool:
        return self.status in (FixStatus.VERIFIED, FixStatus.UNVERIFIED) and bool(self.changes)
