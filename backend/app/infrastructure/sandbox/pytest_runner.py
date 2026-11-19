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
    "python",
    "-m",
    "pytest",
    "-q",
    "-rfE",
    "--tb=short",
    "--no-header",
    "-p",
    "no:cacheprovider",
]


def parse_pytest_output(output: str) -> tuple[dict[str, int], tuple[str, ...]]:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    lines = output.splitlines()

    for line in reversed(lines):
        if _SUMMARY_LINE.search(line):
            for number, label in _COUNT.findall(line):
                key = "errors" if label.startswith("error") else label
                counts[key] += int(number)
            break

    failures = tuple(line[:200] for line in lines if line.startswith(("FAILED ", "ERROR ")))

    return counts, failures


def _has_summary(output: str) -> bool:
    return any(_SUMMARY_LINE.search(line) for line in output.splitlines())


def _status(result: ExecResult) -> SuiteStatus:
    if result.timed_out:
        return SuiteStatus.TIMED_OUT

    return {
        0: SuiteStatus.PASSED,
        1: SuiteStatus.FAILED,
        5: SuiteStatus.NO_TESTS,
    }.get(result.exit_code, SuiteStatus.ERROR)


class PytestRunner:
    """Installs wheel-only dependencies, then runs pytest offline."""

    def __init__(self, sandbox: SandboxPort, timeout_seconds: int = 300) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(
        self,
        workspace: Workspace,
        *,
        install_dependencies: bool = True,
    ) -> SuiteResult:
        project = detect_python_project(workspace.source)

        notes: list[str] = []
        validation_errors: list[str] = []

        if install_dependencies:
            specs = collect_requirement_specs(workspace.source / project)

            if specs:
                install = await self._sandbox.run(
                    workspace,
                    [
                        "python",
                        "-m",
                        "pip",
                        "install",
                        "--target",
                        "/deps",
                        "--only-binary=:all:",
                        "--no-input",
                        *specs,
                    ],
                    workdir=project,
                    timeout_seconds=self._timeout,
                    install_mode=True,
                )

                if not install.ok:
                    message = (
                        f"dependency installation failed "
                        f"({describe_failure(install)}); "
                        "tests may fail on imports"
                    )
                    notes.append(message)
                    validation_errors.append(message)

            else:
                notes.append("No installable dependency list found.")

        root = posixpath.normpath(posixpath.join("/workspace", project))

        pythonpath = ":".join(
            [
                "/deps",
                root,
                posixpath.join(root, "src"),
            ]
        )

        result = await self._sandbox.run(
            workspace,
            PYTEST_COMMAND,
            workdir=project,
            env={"PYTHONPATH": pythonpath},
            timeout_seconds=self._timeout,
        )

        counts, failures = parse_pytest_output(result.stdout)
        status = _status(result)

        if status in (SuiteStatus.PASSED, SuiteStatus.FAILED):
            if not _has_summary(result.stdout):
                validation_errors.append(
                    "Could not parse the pytest summary. The test result may be incomplete."
                )

        total_failures = counts["failed"] + counts["errors"]

        if status is SuiteStatus.FAILED and total_failures == 0:
            validation_errors.append(
                "Pytest exited with a failure status, but no failed-test "
                "counts could be parsed from its summary."
            )

        # The returned failure list is capped at 50 entries.
        # Compare against the capped size, not the original tuple length.
        failures_truncated = total_failures > min(len(failures), 50)

        if failures_truncated:
            notes.append(
                "The pytest failure list was incomplete. Regression comparison cannot be trusted."
            )

        return SuiteResult(
            status=status,
            passed=counts["passed"],
            failed=counts["failed"],
            errors=counts["errors"],
            skipped=counts["skipped"],
            failures=failures[:50],
            output_tail=(result.stdout + result.stderr)[-4000:],
            duration_seconds=result.duration_seconds,
            notes=tuple(notes),
            validation_errors=tuple(validation_errors),
            failures_truncated=failures_truncated,
        )
