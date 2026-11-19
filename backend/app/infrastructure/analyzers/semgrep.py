import json
from collections.abc import Sequence

from app.application.ports.analyzer_port import AnalyzerPort, AnalyzerResult
from app.application.ports.sandbox_port import SandboxPort, Workspace
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity


class SemgrepAnalyzer(AnalyzerPort):
    name = "semgrep"

    def __init__(self, sandbox: SandboxPort) -> None:
        self._sandbox = sandbox

    @staticmethod
    def _severity(value: str) -> Severity:
        return {
            "ERROR": Severity.HIGH,
            "WARNING": Severity.MEDIUM,
            "INFO": Severity.LOW,
        }.get(value.upper(), Severity.MEDIUM)

    @staticmethod
    def _category(metadata: dict, check_id: str) -> FindingCategory:
        category = str(metadata.get("category", "")).lower()
        check_id = check_id.lower()

        if (
            "security" in category
            or "security" in check_id
            or "owasp" in check_id
            or "cwe" in check_id
        ):
            return FindingCategory.SECURITY

        if category in {"correctness", "bug-risk"}:
            return FindingCategory.BUG

        if category in {"performance", "maintainability"}:
            return FindingCategory.CODE_SMELL

        return FindingCategory.CODE_SMELL

    async def run(self, workspace: Workspace, paths: Sequence[str]) -> AnalyzerResult:
        if not paths:
            return AnalyzerResult(tool=self.name)

        try:
            result = await self._sandbox.run(
                workspace,
                ["semgrep", "scan", "--json", "--quiet", "--", *paths],
                timeout_seconds=90,
                env={
                    "SEMGREP_SEND_METRICS": "off",
                    "SEMGREP_ENABLE_VERSION_CHECK": "0",
                },
            )
        except Exception as exc:
            return AnalyzerResult(tool=self.name, error=str(exc))

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return AnalyzerResult(
                tool=self.name,
                error=f"Could not parse Semgrep JSON output: {exc}",
            )

        if not isinstance(payload, dict):
            return AnalyzerResult(
                tool=self.name,
                error="Unexpected Semgrep JSON output format",
            )

        findings: list[Finding] = []

        for item in payload.get("results", []):
            extra = item.get("extra") or {}
            metadata = extra.get("metadata") or {}
            start = item.get("start") or {}
            end = item.get("end") or {}

            check_id = str(item.get("check_id") or "semgrep")
            message = str(extra.get("message") or "Semgrep issue detected")

            path = str(item.get("path") or "")
            path = path.replace("\\", "/")

            if path.startswith("/workspace/"):
                path = path[len("/workspace/") :]

            line_start = start.get("line")
            line_end = end.get("line", line_start)

            severity_value = str(extra.get("severity") or "WARNING")
            fix = extra.get("fix")

            findings.append(
                Finding(
                    category=self._category(metadata, check_id),
                    severity=self._severity(severity_value),
                    title=f"{check_id}: {message}",
                    description=message,
                    source=self.name,
                    file_path=path or None,
                    line_start=(line_start if isinstance(line_start, int) else None),
                    line_end=(line_end if isinstance(line_end, int) else None),
                    suggestion=fix if isinstance(fix, str) else None,
                )
            )

        errors = payload.get("errors") or []
        error = None

        if result.timed_out:
            error = "Semgrep execution timed out"
        elif result.truncated:
            error = "Semgrep output was truncated"
        elif errors:
            error = "; ".join(
                str(item.get("message", item)) if isinstance(item, dict) else str(item)
                for item in errors
            )
        elif result.exit_code != 0 and not findings:
            error = result.stderr.strip() or (f"Semgrep exited with code {result.exit_code}")

        return AnalyzerResult(
            tool=self.name,
            findings=tuple(findings),
            error=error,
        )
