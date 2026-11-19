from pathlib import Path

from app.application.fix_engine import (
    FixEngine,
    FixSettings,
    Measurement,
    failed_test_ids,
    find_regressions,
)
from app.application.ports.sandbox_port import Workspace
from app.application.ports.validation_port import SuiteResult, SuiteStatus
from app.application.workflow.agents.fixer import FixerAgent
from app.application.workflow.schemas import EditOut, FileFixOut
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, FixStatus, Severity
from app.domain.services.fix_planning import plan_fixes
from app.infrastructure.sandbox.workspace_files import WorkspaceFiles
from tests.fakes import FakeLLM, FakeSuiteRunner, FakeWorkspaces, make_pr

ORIGINAL = (
    "import os\n\n\ndef login(user, password):\n"
    "    if password == 'x':\n        return True\n    return False\n"
)
OLD_LINE = "    if password == 'x':\n"
NEW_LINE = "    if verify(user, password):\n"
FINDING = Finding(
    FindingCategory.BUG, Severity.HIGH, "Hardcoded password", "d", "reviewer", "src/a.py", 5, 5
)
PASSED = SuiteResult(SuiteStatus.PASSED, passed=3)
BROKEN = SuiteResult(
    SuiteStatus.FAILED,
    passed=2,
    failed=1,
    failures=("FAILED tests/test_a.py::test_login - assert 1 == 2",),
    output_tail="boom",
)


def edit_out(old: str, new: str) -> FileFixOut:
    return FileFixOut(edits=[EditOut(old_text=old, new_text=new)], explanation="Use verify()")


def setup(tmp_path: Path, llm: FakeLLM, suites=None, **settings):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "a.py").write_bytes(ORIGINAL.encode())
    workspace = Workspace(source, tmp_path / "deps")
    runner = FakeSuiteRunner(suites) if suites else None
    engine = FixEngine(
        workspaces=FakeWorkspaces(workspace=workspace),
        files=WorkspaceFiles(),
        fixer=FixerAgent(llm),
        suite_runner=runner,
        settings=FixSettings(**settings),
    )
    return engine, runner


async def run(engine: FixEngine):
    pr = make_pr()
    return await engine.run(pr, plan_fixes([FINDING], pr.files), [FINDING])


async def test_verified_when_tests_still_pass(tmp_path: Path) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})
    engine, runner = setup(tmp_path, llm, [PASSED])
    proposal = await run(engine)

    assert proposal.status is FixStatus.VERIFIED
    assert proposal.attempts == 1
    assert proposal.base_sha == "abc123"
    (change,) = proposal.changes
    assert change.old_content == ORIGINAL
    assert change.new_content == ORIGINAL.replace(OLD_LINE, NEW_LINE)
    assert runner.calls == [True, False]  # dependencies are installed once, for the baseline


async def test_unverified_when_no_checks_are_available(tmp_path: Path) -> None:
    engine, _ = setup(tmp_path, FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)}))
    proposal = await run(engine)
    assert proposal.status is FixStatus.UNVERIFIED
    assert any("not validated" in note for note in proposal.notes)


async def test_regression_triggers_a_retry_with_the_failure_output(tmp_path: Path) -> None:
    llm = FakeLLM(
        {
            "fixer": [
                edit_out(OLD_LINE, NEW_LINE),
                edit_out("    if verify(user, password):\n", "    if check(user, password):\n"),
            ]
        }
    )
    engine, _ = setup(tmp_path, llm, [PASSED, BROKEN, PASSED])
    proposal = await run(engine)

    assert proposal.status is FixStatus.VERIFIED
    assert proposal.attempts == 2
    assert "check(user, password)" in proposal.changes[0].new_content
    retry_prompt = llm.calls[1]["user"]
    assert "New failing tests" in retry_prompt
    assert "tests/test_a.py::test_login" in retry_prompt


async def test_failures_that_already_existed_are_not_blamed(tmp_path: Path) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})
    engine, _ = setup(tmp_path, llm, [BROKEN, BROKEN])
    assert (await run(engine)).status is FixStatus.VERIFIED


async def test_gives_up_and_proposes_nothing_after_max_attempts(tmp_path: Path) -> None:
    llm = FakeLLM(
        {
            "fixer": [
                edit_out(OLD_LINE, NEW_LINE),
                edit_out("    if verify(user, password):\n", "    if check(user, password):\n"),
            ]
        }
    )
    engine, _ = setup(tmp_path, llm, [PASSED, BROKEN], max_attempts=2)
    proposal = await run(engine)
    assert proposal.status is FixStatus.FAILED
    assert proposal.attempts == 2
    assert proposal.changes == ()


async def test_rejected_edit_is_reported_back_to_the_model(tmp_path: Path) -> None:
    llm = FakeLLM({"fixer": [edit_out("nope\n", "x\n"), edit_out(OLD_LINE, NEW_LINE)]})
    engine, _ = setup(tmp_path, llm)
    proposal = await run(engine)
    assert proposal.status is FixStatus.UNVERIFIED
    assert proposal.attempts == 2
    assert "not found" in llm.calls[1]["user"]


async def test_edits_that_break_python_syntax_never_reach_the_disk(tmp_path: Path) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, "    if (:\n")})
    engine, _ = setup(tmp_path, llm, max_attempts=1)
    proposal = await run(engine)
    assert proposal.status is FixStatus.FAILED
    assert (tmp_path / "source" / "src" / "a.py").read_text() == ORIGINAL


async def test_oversized_edits_are_rejected(tmp_path: Path) -> None:
    llm = FakeLLM(
        {
            "fixer": edit_out(
                OLD_LINE + "        return True\n", "    return verify(user, password)\n"
            )
        }
    )
    engine, _ = setup(tmp_path, llm, max_attempts=1, max_changed_lines=1)
    assert (await run(engine)).status is FixStatus.FAILED


async def test_no_edits_means_nothing_to_fix(tmp_path: Path) -> None:
    llm = FakeLLM({"fixer": FileFixOut(edits=[], explanation="false positive")})
    engine, _ = setup(tmp_path, llm)
    assert (await run(engine)).status is FixStatus.NOTHING_TO_FIX


def measurement(findings=None, failed=(), status=SuiteStatus.PASSED, tail="") -> Measurement:
    return Measurement(
        findings=findings or {},
        failed_tests=frozenset(failed),
        suite_status=status,
        output_tail=tail,
    )


def test_no_regression_when_nothing_is_new() -> None:
    assert find_regressions(measurement(failed=["a"]), measurement(failed=["a"])) == []


def test_new_failures_are_reported_with_the_output_tail() -> None:
    problems = find_regressions(measurement(), measurement(failed=["t::x"], tail="boom"))
    assert "t::x" in problems[0] and "boom" in problems[0]


def test_new_static_findings_are_regressions() -> None:
    key = ("ruff", "F821: Undefined name", "a.py")
    assert find_regressions(measurement({key: 1}), measurement({key: 1})) == []
    assert find_regressions(measurement({key: 1}), measurement({key: 2}))


def test_a_timeout_after_a_clean_baseline_is_a_regression() -> None:
    after = measurement(status=SuiteStatus.TIMED_OUT)
    assert find_regressions(measurement(), after)


def test_failed_test_ids_drop_the_message() -> None:
    suite = SuiteResult(
        SuiteStatus.FAILED, failures=("FAILED t.py::a - boom", "ERROR t.py::b - bad import")
    )
    assert failed_test_ids(suite) == {"t.py::a", "t.py::b"}
