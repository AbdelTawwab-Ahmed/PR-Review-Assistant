import json
import re
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity
from app.infrastructure.analyzers.common import container_paths, describe_failure, repo_path

_SECURITY = re.compile(r"^S\d+$")  # flake8-bandit, not SIM/SLF
_BUGLIKE = re.compile(r"^[BF]\d+$")  # pyflakes, bugbear
HIGH_PREFIXES = ("E9", "F63", "F7", "F82")  # syntax errors, undefined names
NOISY_CODES = frozenset({"F401", "F841"})  # unused imports and variables


def _severity(code: str) -> Severity:
    if code == "syntax-error" or code.startswith(HIGH_PREFIXES):
        return Severity.HIGH
    if code in NOISY_CODES:
        return Severity.LOW
    if _SECURITY.match(code) or _BUGLIKE.match(code):
        return Severity.MEDIUM
    return Severity.LOW


def _category(code: str) -> FindingCategory:
    if _SECURITY.match(code):
        return FindingCategory.SECURITY
    if code == "syntax-error" or _BUGLIKE.match(code):
        return FindingCategory.BUG
    return FindingCategory.STYLE


def parse_ruff(stdout: str) -> list[Finding]:
    findings: list[Finding] = []
    for item in json.loads(stdout.strip() or "[]"):
        code = item.get("code") or "syntax-error"
        row = item["location"]["row"]
        end = (item.get("end_location") or {}).get("row")
        description = item["message"]
        if item.get("url"):
            description += f"\nDocs: {item['url']}"
        findings.append(
            Finding(
                category=_category(code),
                severity=_severity(code),
                title=f"{code}: {item['message']}"[:120],
                description=description,
                source="ruff",
                file_path=repo_path(item["filename"]),
                line_start=row,
                line_end=end if end and end >= row else None,
                suggestion=(item.get("fix") or {}).get("message"),
            )
        )
    return findings


class RuffAnalyzer:
    name = "ruff"

    def __init__(self, sandbox: SandboxPort, timeout_seconds: int = 60) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        targets = container_paths(paths, (".py",))
        if not targets:
            return AnalyzerResult(self.name)
        command = [
            "ruff",
            "check",
            "--output-format",
            "json",
            "--no-cache",
            "--exit-zero",
            *targets,
        ]
        result = await self._sandbox.run(workspace, command, timeout_seconds=self._timeout)
        if not result.ok:
            return AnalyzerResult(self.name, error=describe_failure(result))
        try:
            findings = parse_ruff(result.stdout)
        except (ValueError, KeyError, TypeError):
            return AnalyzerResult(self.name, error="could not parse ruff output")
        return AnalyzerResult(self.name, tuple(findings))
