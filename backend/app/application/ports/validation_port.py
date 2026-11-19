from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.application.ports.sandbox_port import Workspace


class SuiteStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NO_TESTS = "no_tests"
    ERROR = "error"  # collection errors, internal errors, bad usage
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class SuiteResult:
    status: SuiteStatus
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failures: tuple[str, ...] = ()
    output_tail: str = ""
    duration_seconds: float = 0.0
    notes: tuple[str, ...] = ()


class SuiteRunnerPort(Protocol):
    async def run(
        self, workspace: Workspace, *, install_dependencies: bool = True
    ) -> SuiteResult: ...
