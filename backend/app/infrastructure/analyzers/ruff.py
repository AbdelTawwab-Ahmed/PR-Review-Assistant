import json
import re
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

_SECURITY = re.compile(r"^S\d+$")
_BUGLIKE = re.compile(r"^[BF]\d+$")

HIGH_PREFIXES = ("E9", "F63", "F7", "F82")
NOISY_CODES = frozenset({"F401", "F841"})


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
    payload = json.loads(stdout.strip() or "[]")

    if not isinstance(payload, list):
        raise ValueError("Unexpected Ruff JSON output format")

    findings: list[Finding] = []

    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Unexpected Ruff finding format")

        code = str(item.get("code") or "syntax-error")
        message = str(item.get("message") or "Lint issue detected")

        location = item.get("location") or {}
        end_location = item.get("end_location") or {}

        row = location.get("row")
        end = end_location.get("row")

        description = message
        if item.get("url"):
            description += f"\nDocs: {item['url']}"

        filename = repo_path(str(item.get("filename") or ""))
        fix = item.get("fix") or {}

        findings.append(
            Finding(
                category=_category(code),
                severity=_severity(code),
                title=f"{code}: {message}"[:120],
                description=description,
                source="ruff",
                file_path=filename or None,
                line_start=row if isinstance(row, int) else None,
                line_end=(
                    end if isinstance(end, int) and isinstance(row, int) and end >= row else None
                ),
                suggestion=fix.get("message"),
            )
        )

    return findings


class RuffAnalyzer(AnalyzerPort):
    name = "ruff"

    def __init__(
        self,
        sandbox: SandboxPort,
        timeout_seconds: int = 60,
    ) -> None:
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        targets = container_paths(paths, (".py",))

        if not targets:
            return AnalyzerResult(tool=self.name)

        command = [
            "ruff",
            "check",
            "--output-format",
            "json",
            "--no-cache",
            "--exit-zero",
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
            findings = parse_ruff(result.stdout)
        except (ValueError, KeyError, TypeError):
            return AnalyzerResult(
                tool=self.name,
                error="could not parse ruff output",
            )

        return AnalyzerResult(
            tool=self.name,
            findings=tuple(findings),
        )
