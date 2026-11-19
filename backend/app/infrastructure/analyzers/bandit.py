import json
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerPort, AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity
from app.infrastructure.analyzers.common import (
    container_paths,
    describe_failure,
    is_test_path,
    repo_path,
)

_SEVERITY = {
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
}


def parse_bandit(stdout: str) -> list[Finding]:
    payload = json.loads(stdout or "{}")
    findings: list[Finding] = []

    for item in payload.get("results", []):
        lines = item.get("line_range") or []
        start = item.get("line_number")
        end = lines[-1] if lines and isinstance(start, int) and lines[-1] >= start else None

        description = str(item.get("issue_text") or "Security issue detected")
        more_info = item.get("more_info")
        if more_info:
            description += f"\nDocs: {more_info}"

        test_id = str(item.get("test_id") or "Bandit")
        test_name = str(item.get("test_name") or "security issue")
        confidence = item.get("issue_confidence")

        if confidence:
            description += f"\nConfidence: {confidence}"

        filename = repo_path(str(item.get("filename") or ""))

        findings.append(
            Finding(
                category=FindingCategory.SECURITY,
                severity=_SEVERITY.get(
                    str(item.get("issue_severity") or "LOW").upper(),
                    Severity.LOW,
                ),
                title=f"{test_id}: {test_name.replace('_', ' ')}"[:120],
                description=description,
                source="bandit",
                file_path=filename or None,
                line_start=start if isinstance(start, int) else None,
                line_end=end,
            )
        )

    return findings


class BanditAnalyzer(AnalyzerPort):
    name = "bandit"

    def __init__(
        self,
        sandbox: SandboxPort,
        timeout_seconds: int = 60,
    ) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        targets = [path for path in container_paths(paths, (".py",)) if not is_test_path(path)]

        if not targets:
            return AnalyzerResult(tool=self.name)

        try:
            result = await self._sandbox.run(
                workspace,
                ["bandit", "-f", "json", "-q", "--exit-zero", *targets],
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
            findings = parse_bandit(result.stdout)
        except (ValueError, KeyError, TypeError):
            return AnalyzerResult(
                tool=self.name,
                error="could not parse bandit output",
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
