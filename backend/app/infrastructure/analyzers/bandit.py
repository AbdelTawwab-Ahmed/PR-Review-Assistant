import json
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerPort, AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity


class BanditAnalyzer(AnalyzerPort):
    name = "bandit"

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        if not paths:
            return AnalyzerResult(tool=self.name)

        try:
            result = await self._sandbox.run(
                workspace,
                ["bandit", "-f", "json", "-q", "--", *paths],
                timeout_seconds=60,
            )
        except Exception as exc:
            return AnalyzerResult(tool=self.name, error=str(exc))

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return AnalyzerResult(
                tool=self.name,
                error=f"Could not parse Bandit JSON output: {exc}",
            )

        findings: list[Finding] = []

        for item in payload.get("results", []):
            severity_value = str(item.get("issue_severity", "LOW")).upper()

            severity = {
                "HIGH": Severity.HIGH,
                "MEDIUM": Severity.MEDIUM,
                "LOW": Severity.LOW,
            }.get(severity_value, Severity.MEDIUM)

            filename = str(item.get("filename", ""))
            filename = filename.replace("\\", "/")

            if filename.startswith("/workspace/"):
                filename = filename[len("/workspace/") :]

            test_id = str(item.get("test_id", "Bandit"))
            issue_text = str(item.get("issue_text", "Security issue detected"))
            confidence = item.get("issue_confidence", "UNKNOWN")
            line = item.get("line_number")

            findings.append(
                Finding(
                    category=FindingCategory.SECURITY,
                    severity=severity,
                    title=f"{test_id}: {issue_text}",
                    description=(f"{issue_text}\nConfidence: {confidence}"),
                    source=self.name,
                    file_path=filename or None,
                    line_start=line if isinstance(line, int) else None,
                    line_end=line if isinstance(line, int) else None,
                    suggestion=None,
                )
            )

        error = None
        if result.timed_out:
            error = "Bandit execution timed out"
        elif result.truncated:
            error = "Bandit output was truncated"
        elif result.exit_code not in (0, 1) and not findings:
            error = result.stderr.strip() or (f"Bandit exited with code {result.exit_code}")

        return AnalyzerResult(
            tool=self.name,
            findings=tuple(findings),
            error=error,
        )
