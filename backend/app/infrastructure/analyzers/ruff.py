import json
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerPort, AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity


class RuffAnalyzer(AnalyzerPort):
    name = "ruff"

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    @staticmethod
    def _category(code: str) -> FindingCategory:
        prefix = code.upper()

        if prefix.startswith("S"):
            return FindingCategory.SECURITY

        if prefix.startswith(("F", "B")):
            return FindingCategory.BUG

        if prefix.startswith(("C", "PL")):
            return FindingCategory.CODE_SMELL

        return FindingCategory.STYLE

    @staticmethod
    def _severity(code: str) -> Severity:
        code = code.upper()

        if code.startswith(("F", "S", "B")):
            return Severity.HIGH

        if code.startswith(("E", "C", "PL")):
            return Severity.MEDIUM

        return Severity.LOW

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        if not paths:
            return AnalyzerResult(tool=self.name)

        try:
            result = await self._sandbox.run(
                workspace,
                ["ruff", "check", "--output-format=json", "--", *paths],
                timeout_seconds=60,
            )
        except Exception as exc:
            return AnalyzerResult(tool=self.name, error=str(exc))

        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return AnalyzerResult(
                tool=self.name,
                error=f"Could not parse Ruff JSON output: {exc}",
            )

        findings: list[Finding] = []

        if not isinstance(payload, list):
            return AnalyzerResult(
                tool=self.name,
                error="Unexpected Ruff JSON output format",
            )

        for item in payload:
            code = str(item.get("code") or "RUFF")
            message = str(item.get("message") or "Lint issue detected")

            filename = str(item.get("filename") or "")
            filename = filename.replace("\\", "/")

            if filename.startswith("/workspace/"):
                filename = filename[len("/workspace/") :]

            location = item.get("location") or {}
            end_location = item.get("end_location") or {}

            line_start = location.get("row")
            line_end = end_location.get("row", line_start)

            fix = item.get("fix") or {}
            suggestion = fix.get("message")

            findings.append(
                Finding(
                    category=self._category(code),
                    severity=self._severity(code),
                    title=f"{code}: {message}",
                    description=message,
                    source=self.name,
                    file_path=filename or None,
                    line_start=(line_start if isinstance(line_start, int) else None),
                    line_end=(line_end if isinstance(line_end, int) else None),
                    suggestion=suggestion,
                )
            )

        error = None
        if result.timed_out:
            error = "Ruff execution timed out"
        elif result.truncated:
            error = "Ruff output was truncated"
        elif result.exit_code not in (0, 1) and not findings:
            error = result.stderr.strip() or (f"Ruff exited with code {result.exit_code}")

        return AnalyzerResult(
            tool=self.name,
            findings=tuple(findings),
            error=error,
        )
