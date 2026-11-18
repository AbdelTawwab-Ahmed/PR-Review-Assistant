import json
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity
from app.infrastructure.analyzers.common import (
    container_paths,
    describe_failure,
    is_test_path,
    repo_path,
)

_SEVERITY = {"HIGH": Severity.HIGH, "MEDIUM": Severity.MEDIUM, "LOW": Severity.LOW}


def parse_bandit(stdout: str) -> list[Finding]:
    findings: list[Finding] = []
    for item in json.loads(stdout)["results"]:
        lines = item.get("line_range") or []
        start = item["line_number"]
        end = lines[-1] if lines and lines[-1] >= start else None
        description = item["issue_text"]
        if item.get("more_info"):
            description += f"\nDocs: {item['more_info']}"
        findings.append(
            Finding(
                category=FindingCategory.SECURITY,
                severity=_SEVERITY.get(item["issue_severity"], Severity.LOW),
                title=f"{item['test_id']}: {item['test_name'].replace('_', ' ')}"[:120],
                description=description,
                source="bandit",
                file_path=repo_path(item["filename"]),
                line_start=start,
                line_end=end,
            )
        )
    return findings


class BanditAnalyzer:
    name = "bandit"

    def __init__(self, sandbox: SandboxPort, timeout_seconds: int = 60) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        # Tests legitimately use assert and fake passwords, so they are not scanned.
        targets = [p for p in container_paths(paths, (".py",)) if not is_test_path(p)]
        if not targets:
            return AnalyzerResult(self.name)
        command = ["bandit", "-f", "json", "-q", "--exit-zero", *targets]
        result = await self._sandbox.run(workspace, command, timeout_seconds=self._timeout)
        if not result.ok:
            return AnalyzerResult(self.name, error=describe_failure(result))
        try:
            findings = parse_bandit(result.stdout)
        except (ValueError, KeyError, TypeError):
            return AnalyzerResult(self.name, error="could not parse bandit output")
        return AnalyzerResult(self.name, tuple(findings))
