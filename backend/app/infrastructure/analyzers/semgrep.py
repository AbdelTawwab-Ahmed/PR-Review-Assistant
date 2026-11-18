import json
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity
from app.infrastructure.analyzers.common import container_paths, describe_failure, repo_path

SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")
RULE_DIRS = ("/opt/rules/python", "/opt/rules/javascript", "/opt/rules/typescript")
_SEVERITY = {"ERROR": Severity.HIGH, "WARNING": Severity.MEDIUM, "INFO": Severity.LOW}
_CATEGORY = {"security": FindingCategory.SECURITY, "correctness": FindingCategory.BUG}


def parse_semgrep(stdout: str) -> list[Finding]:
    findings: list[Finding] = []
    for item in json.loads(stdout)["results"]:
        extra = item["extra"]
        category = (extra.get("metadata") or {}).get("category", "security")
        start = item["start"]["line"]
        end = item["end"]["line"]
        findings.append(
            Finding(
                category=_CATEGORY.get(category, FindingCategory.CODE_SMELL),
                severity=_SEVERITY.get(extra.get("severity", "WARNING"), Severity.MEDIUM),
                title=item["check_id"].rsplit(".", 1)[-1][:120],
                description=extra["message"],
                source="semgrep",
                file_path=repo_path(item["path"]),
                line_start=start,
                line_end=end if end >= start else None,
            )
        )
    return findings


class SemgrepAnalyzer:
    name = "semgrep"

    def __init__(self, sandbox: SandboxPort, timeout_seconds: int = 180) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        targets = container_paths(paths, SUFFIXES)
        if not targets:
            return AnalyzerResult(self.name)
        command = [
            "semgrep", "scan", "--json", "--quiet", "--metrics=off",
            "--disable-version-check", "--no-git-ignore", "--timeout", "20",
            *[f"--config={rules}" for rules in RULE_DIRS],
            *targets,
        ]  # fmt: skip
        result = await self._sandbox.run(workspace, command, timeout_seconds=self._timeout)
        if not result.ok:
            return AnalyzerResult(self.name, error=describe_failure(result))
        try:
            findings = parse_semgrep(result.stdout)
        except (ValueError, KeyError, TypeError):
            return AnalyzerResult(self.name, error="could not parse semgrep output")
        return AnalyzerResult(self.name, tuple(findings))
