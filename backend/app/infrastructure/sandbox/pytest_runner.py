import posixpath
import re

from app.application.ports.sandbox_port import ExecResult, SandboxPort, Workspace
from app.application.ports.validation_port import SuiteResult, SuiteStatus
from app.infrastructure.analyzers.common import describe_failure
from app.infrastructure.sandbox.python_project import (
    collect_requirement_specs,
    detect_python_project,
)

_SUMMARY_LINE = re.compile(r" in [\d.]+s")
_COUNT = re.compile(r"(\d+) (passed|failed|errors?|skipped)")
PYTEST_COMMAND = [
    "python", "-m", "pytest", "-q", "-rfE", "--tb=short", "--no-header", "-p", "no:cacheprovider",
]  # fmt: skip


def parse_pytest_output(output: str) -> tuple[dict[str, int], tuple[str, ...]]:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    lines = output.splitlines()
    for line in reversed(lines):
        if _SUMMARY_LINE.search(line):
            for number, label in _COUNT.findall(line):
                counts["errors" if label.startswith("error") else label] += int(number)
            break
    failures = tuple(line[:200] for line in lines if line.startswith(("FAILED ", "ERROR ")))[:50]
    return counts, failures


def _status(result: ExecResult) -> SuiteStatus:
    if result.timed_out:
        return SuiteStatus.TIMED_OUT
    return {0: SuiteStatus.PASSED, 1: SuiteStatus.FAILED, 5: SuiteStatus.NO_TESTS}.get(
        result.exit_code, SuiteStatus.ERROR
    )


class PytestRunner:
    """Installs wheel-only dependencies (the one networked step), then runs pytest offline."""

    def __init__(self, sandbox: SandboxPort, timeout_seconds: int = 300) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(self, workspace: Workspace, *, install_dependencies: bool = True) -> SuiteResult:
        project = detect_python_project(workspace.source)
        notes: list[str] = []

        if install_dependencies:
            specs = collect_requirement_specs(workspace.source / project)
            if specs:
                install = await self._sandbox.run(
                    workspace,
                    ["python", "-m", "pip", "install", "--target", "/deps",
                     "--only-binary=:all:", "--no-input", *specs],
                    workdir=project,
                    timeout_seconds=self._timeout,
                    install_mode=True,
                )  # fmt: skip
                if not install.ok:
                    notes.append(
                        f"dependency installation failed ({describe_failure(install)}); "
                        "tests may fail on imports"
                    )
            else:
                notes.append("no installable dependency list found")

        root = posixpath.normpath(posixpath.join("/workspace", project))
        pythonpath = ":".join(["/deps", root, posixpath.join(root, "src")])
        result = await self._sandbox.run(
            workspace,
            PYTEST_COMMAND,
            workdir=project,
            env={"PYTHONPATH": pythonpath},
            timeout_seconds=self._timeout,
        )
        counts, failures = parse_pytest_output(result.stdout)
        return SuiteResult(
            status=_status(result),
            passed=counts["passed"],
            failed=counts["failed"],
            errors=counts["errors"],
            skipped=counts["skipped"],
            failures=failures,
            output_tail=(result.stdout + result.stderr)[-4000:],
            duration_seconds=result.duration_seconds,
            notes=tuple(notes),
        )
