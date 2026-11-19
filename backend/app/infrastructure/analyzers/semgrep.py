import json
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerPort, AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity
from app.infrastructure.analyzers.common import (
    container_paths,
    describe_failure,
    repo_path,
)

SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")

RULE_DIRS = (
    "/opt/rules/python",
    "/opt/rules/javascript",
    "/opt/rules/typescript",
)

_SEVERITY = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}

_CATEGORY = {
    "security": FindingCategory.SECURITY,
    "correctness": FindingCategory.BUG,
}


def parse_semgrep(stdout: str) -> list[Finding]:
    payload = json.loads(stdout or "{}")

    if not isinstance(payload, dict):
        raise ValueError("Unexpected Semgrep JSON output format")

    findings: list[Finding] = []

    for item in payload.get("results", []):
        if not isinstance(item, dict):
            raise ValueError("Unexpected Semgrep finding format")

        extra = item.get("extra") or {}
        metadata = extra.get("metadata") or {}

        start = item.get("start") or {}
        end = item.get("end") or {}

        category = str(metadata.get("category") or "").lower()
        severity_value = str(extra.get("severity") or "WARNING").upper()

        check_id = str(item.get("check_id") or "semgrep")
        message = str(extra.get("message") or "Semgrep issue detected")

        line_start = start.get("line")
        line_end = end.get("line")

        filename = repo_path(str(item.get("path") or ""))

        fix = extra.get("fix")

        findings.append(
            Finding(
                category=_CATEGORY.get(category, FindingCategory.CODE_SMELL),
                severity=_SEVERITY.get(severity_value, Severity.MEDIUM),
                title=check_id.rsplit(".", 1)[-1][:120],
                description=message,
                source="semgrep",
                file_path=filename or None,
                line_start=line_start if isinstance(line_start, int) else None,
                line_end=(
                    line_end
                    if isinstance(line_end, int)
                    and isinstance(line_start, int)
                    and line_end >= line_start
                    else None
                ),
                suggestion=fix if isinstance(fix, str) else None,
            )
        )

    return findings


class SemgrepAnalyzer(AnalyzerPort):
    name = "semgrep"

    def __init__(
        self,
        sandbox: SandboxPort,
        timeout_seconds: int = 180,
    ) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        targets = container_paths(paths, SUFFIXES)

        if not targets:
            return AnalyzerResult(tool=self.name)

        command = [
            "semgrep",
            "scan",
            "--json",
            "--quiet",
            "--metrics=off",
            "--disable-version-check",
            "--no-git-ignore",
            "--timeout",
            "20",
            *[f"--config={rules}" for rules in RULE_DIRS],
            *targets,
        ]

        try:
            result = await self._sandbox.run(
                workspace,
                command,
                timeout_seconds=self._timeout,
            )
        except Exception as exc:
            return AnalyzerResult(tool=self.name, error=str(exc))

        if not result.ok:
            return AnalyzerResult(
                tool=self.name,
                error=describe_failure(result),
            )

        try:
            payload = json.loads(result.stdout or "{}")
            findings = parse_semgrep(result.stdout)
        except (ValueError, KeyError, TypeError):
            return AnalyzerResult(
                tool=self.name,
                error="could not parse semgrep output",
            )

        errors = payload.get("errors") or []
        error = None

        if errors:
            error = "; ".join(
                str(item.get("message", item)) if isinstance(item, dict) else str(item)
                for item in errors
            )

        return AnalyzerResult(
            tool=self.name,
            findings=tuple(findings),
            error=error,
        )
