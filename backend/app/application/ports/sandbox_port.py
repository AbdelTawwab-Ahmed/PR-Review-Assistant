from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SandboxError(Exception):
    """The sandbox could not be prepared or started (not: the command inside it failed)."""


@dataclass(frozen=True)
class Workspace:
    source: Path  # extracted repository, mounted read-only into every sandbox run
    deps: Path  # third-party packages for the tests, written only by the install step


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.truncated


class SandboxPort(Protocol):
    async def run(
        self,
        workspace: Workspace,
        command: Sequence[str],
        *,
        workdir: str = ".",
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
        install_mode: bool = False,
    ) -> ExecResult: ...


class WorkspaceProvider(Protocol):
    def open(self, repo_full_name: str, sha: str) -> AbstractAsyncContextManager[Workspace]: ...
