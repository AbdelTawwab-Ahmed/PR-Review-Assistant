from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.application.ports.sandbox_port import Workspace
from app.domain.entities.finding import Finding


@dataclass(frozen=True)
class AnalyzerResult:
    tool: str
    findings: tuple[Finding, ...] = ()
    error: str | None = None  # the tool crashed, timed out or printed unparsable output


class AnalyzerPort(Protocol):
    name: str

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult: ...
