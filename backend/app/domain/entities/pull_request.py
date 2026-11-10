from dataclasses import dataclass


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str  # added | modified | removed | renamed
    additions: int = 0
    deletions: int = 0
    patch: str | None = None

    @property
    def changes(self) -> int:
        return self.additions + self.deletions


@dataclass(frozen=True)
class PullRequest:
    repo_full_name: str
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    head_sha: str
    files: tuple[ChangedFile, ...] = ()
    draft: bool = False

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def total_changes(self) -> int:
        return self.total_additions + self.total_deletions

    @property
    def files_changed(self) -> int:
        return len(self.files)
