import json

from app.application.ports.sandbox_port import ExecResult
from app.domain.enums import FindingCategory, Severity
from app.infrastructure.analyzers.bandit import BanditAnalyzer
from app.infrastructure.analyzers.ruff import RuffAnalyzer
from app.infrastructure.analyzers.semgrep import SemgrepAnalyzer
from tests.fakes import WORKSPACE, FakeSandbox

RUFF = json.dumps(
    [
        {
            "code": "F821", "message": "Undefined name `x`",
            "filename": "/workspace/backend/app/a.py",
            "location": {"row": 4, "column": 1}, "end_location": {"row": 4, "column": 2},
            "fix": None, "url": "https://docs.astral.sh/ruff/rules/undefined-name",
        },
        {
            "code": "E501", "message": "Line too long",
            "filename": "/workspace/backend/app/a.py",
            "location": {"row": 9, "column": 1}, "end_location": {"row": 9, "column": 120},
            "fix": None, "url": None,
        },
        {
            "code": None, "message": "SyntaxError: invalid syntax",
            "filename": "/workspace/b.py",
            "location": {"row": 1, "column": 1}, "end_location": {"row": 1, "column": 2},
            "fix": None, "url": None,
        },
    ]
)  # fmt: skip

BANDIT = json.dumps(
    {
        "results": [
            {
                "filename": "/workspace/app/a.py", "issue_severity": "HIGH",
                "issue_confidence": "HIGH", "issue_text": "Possible hardcoded password",
                "line_number": 3, "line_range": [3], "test_id": "B105",
                "test_name": "hardcoded_password_string", "more_info": "https://bandit.example",
            }
        ],
        "errors": [],
    }
)  # fmt: skip

SEMGREP = json.dumps(
    {
        "results": [
            {
                "check_id": (
            "python.lang.security.audit.dangerous-system-call.dangerous-system-call"
                ),
                "path": "/workspace/app/a.py",
                "start": {"line": 7, "col": 1}, "end": {"line": 8, "col": 10},
                "extra": {
                    "message": "Detected a system call with user input.",
                    "severity": "ERROR", "metadata": {"category": "security"},
                },
            }
        ],
        "errors": [],
    }
)  # fmt: skip


async def test_ruff_parses_findings_and_maps_severity() -> None:
    sandbox = FakeSandbox([ExecResult(0, RUFF, "")])
    result = await RuffAnalyzer(sandbox).run(WORKSPACE, ["backend/app/a.py", "README.md", "b.py"])

    assert sandbox.calls[0]["command"][-2:] == ["/workspace/backend/app/a.py", "/workspace/b.py"]
    by_code = {f.title.split(":")[0]: f for f in result.findings}
    assert by_code["F821"].severity is Severity.HIGH
    assert by_code["F821"].file_path == "backend/app/a.py"
    assert by_code["F821"].line_start == 4
    assert by_code["E501"].category is FindingCategory.STYLE
    assert by_code["syntax-error"].severity is Severity.HIGH


async def test_ruff_skips_the_sandbox_when_there_are_no_python_files() -> None:
    sandbox = FakeSandbox()
    result = await RuffAnalyzer(sandbox).run(WORKSPACE, ["README.md"])
    assert result.findings == () and sandbox.calls == []


async def test_tool_failures_become_errors_not_exceptions() -> None:
    crashed = await RuffAnalyzer(FakeSandbox([ExecResult(2, "", "boom")])).run(WORKSPACE, ["a.py"])
    assert crashed.error is not None and "exit code 2" in crashed.error

    slow = ExecResult(-1, "", "", timed_out=True)
    assert (await RuffAnalyzer(FakeSandbox([slow])).run(WORKSPACE, ["a.py"])).error == "timed out"

    garbage = await RuffAnalyzer(FakeSandbox([ExecResult(0, "not json", "")])).run(
        WORKSPACE, ["a.py"]
    )
    assert garbage.error == "could not parse ruff output"


async def test_bandit_parses_and_skips_test_files() -> None:
    sandbox = FakeSandbox([ExecResult(0, BANDIT, "")])
    result = await BanditAnalyzer(sandbox).run(WORKSPACE, ["app/a.py", "tests/test_a.py"])

    assert sandbox.calls[0]["command"][-1:] == ["/workspace/app/a.py"]
    (finding,) = result.findings
    assert finding.category is FindingCategory.SECURITY
    assert finding.severity is Severity.HIGH
    assert finding.title.startswith("B105")


async def test_semgrep_parses_findings_and_uses_the_baked_in_rules() -> None:
    sandbox = FakeSandbox([ExecResult(0, SEMGREP, "")])
    result = await SemgrepAnalyzer(sandbox).run(WORKSPACE, ["app/a.py", "web/app.tsx", "notes.md"])

    command = sandbox.calls[0]["command"]
    assert "--config=/opt/rules/python" in command
    assert "--metrics=off" in command
    assert command[-2:] == ["/workspace/app/a.py", "/workspace/web/app.tsx"]
    (finding,) = result.findings
    assert finding.source == "semgrep"
    assert finding.title == "dangerous-system-call"
    assert (finding.severity, finding.category) == (Severity.HIGH, FindingCategory.SECURITY)
    assert (finding.line_start, finding.line_end) == (7, 8)
