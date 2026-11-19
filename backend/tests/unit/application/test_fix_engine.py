from pathlib import Path

import pytest

from app.application.fix_engine import (
    FixEngine,
    FixSettings,
    Measurement,
    failed_test_ids,
    find_regressions,
)
from app.application.ports.analyzer_port import AnalyzerResult
from app.application.ports.sandbox_port import Workspace
from app.application.ports.validation_port import SuiteResult, SuiteStatus
from app.application.workflow.agents.fixer import FileFix, FixerAgent
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
    FindingCategory.BUG,
    Severity.HIGH,
    "Hardcoded password",
    "d",
    "reviewer",
    "src/a.py",
    5,
    5,
)

PASSED = SuiteResult(SuiteStatus.PASSED, passed=3)

BROKEN = SuiteResult(
    SuiteStatus.FAILED,
    passed=2,
    failed=1,
    failures=("FAILED tests/test_a.py::test_login - assert 1 == 2",),
    output_tail="boom",
)

NO_TESTS = SuiteResult(SuiteStatus.NO_TESTS)


class FakeAnalyzer:
    name = "fake-analyzer"

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.calls = 0

    async def run(self, workspace: Workspace, paths):
        self.calls += 1
        return AnalyzerResult(
            tool=self.name,
            error=self.error,
        )


def edit_out(old: str, new: str) -> FileFixOut:
    return FileFixOut(
        edits=[EditOut(old_text=old, new_text=new)],
        explanation="Use verify()",
    )


def setup(
    tmp_path: Path,
    llm: FakeLLM,
    suites=None,
    analyzers=(),
    **settings,
):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "a.py").write_bytes(ORIGINAL.encode())

    workspace = Workspace(source, tmp_path / "deps")
    runner = FakeSuiteRunner(suites) if suites else None

    engine = FixEngine(
        workspaces=FakeWorkspaces(workspace=workspace),
        files=WorkspaceFiles(),
        fixer=FixerAgent(llm),
        analyzers=tuple(analyzers),
        suite_runner=runner,
        settings=FixSettings(**settings),
    )

    return engine, runner


async def run(engine: FixEngine):
    pr = make_pr()
    return await engine.run(
        pr,
        plan_fixes([FINDING], pr.files),
        [FINDING],
    )


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
    assert runner.calls == [True, False]


async def test_unverified_when_no_checks_are_available(
    tmp_path: Path,
) -> None:
    engine, _ = setup(
        tmp_path,
        FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)}),
    )

    proposal = await run(engine)

    assert proposal.status is FixStatus.UNVERIFIED
    assert any("not validated" in note for note in proposal.notes)


async def test_regression_triggers_a_retry_with_the_failure_output(
    tmp_path: Path,
) -> None:
    llm = FakeLLM(
        {
            "fixer": [
                edit_out(OLD_LINE, NEW_LINE),
                edit_out(
                    "    if verify(user, password):\n",
                    "    if check(user, password):\n",
                ),
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


async def test_failures_that_already_existed_are_not_blamed(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})
    engine, _ = setup(tmp_path, llm, [BROKEN, BROKEN])

    assert (await run(engine)).status is FixStatus.VERIFIED


async def test_gives_up_and_proposes_nothing_after_max_attempts(
    tmp_path: Path,
) -> None:
    llm = FakeLLM(
        {
            "fixer": [
                edit_out(OLD_LINE, NEW_LINE),
                edit_out(
                    "    if verify(user, password):\n",
                    "    if check(user, password):\n",
                ),
            ]
        }
    )

    engine, _ = setup(
        tmp_path,
        llm,
        [PASSED, BROKEN],
        max_attempts=2,
    )

    proposal = await run(engine)

    assert proposal.status is FixStatus.FAILED
    assert proposal.attempts == 2
    assert proposal.changes == ()


async def test_rejected_edit_is_reported_back_to_the_model(
    tmp_path: Path,
) -> None:
    llm = FakeLLM(
        {
            "fixer": [
                edit_out("nope\n", "x\n"),
                edit_out(OLD_LINE, NEW_LINE),
            ]
        }
    )

    engine, _ = setup(tmp_path, llm)

    proposal = await run(engine)

    assert proposal.status is FixStatus.UNVERIFIED
    assert proposal.attempts == 2
    assert "not found" in llm.calls[1]["user"]


async def test_edits_that_break_python_syntax_never_reach_the_disk(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, "    if (:\n")})

    engine, _ = setup(tmp_path, llm, max_attempts=1)

    proposal = await run(engine)

    assert proposal.status is FixStatus.FAILED
    assert (tmp_path / "source" / "src" / "a.py").read_text() == ORIGINAL


async def test_oversized_edits_are_rejected(tmp_path: Path) -> None:
    llm = FakeLLM(
        {
            "fixer": edit_out(
                OLD_LINE + "        return True\n",
                "    return verify(user, password)\n",
            )
        }
    )

    engine, _ = setup(
        tmp_path,
        llm,
        max_attempts=1,
        max_changed_lines=1,
    )

    assert (await run(engine)).status is FixStatus.FAILED


async def test_no_edits_means_nothing_to_fix(tmp_path: Path) -> None:
    llm = FakeLLM(
        {
            "fixer": FileFixOut(
                edits=[],
                explanation="false positive",
            )
        }
    )

    engine, _ = setup(tmp_path, llm)

    assert (await run(engine)).status is FixStatus.NOTHING_TO_FIX


def measurement(
    findings=None,
    failed=(),
    status=SuiteStatus.PASSED,
    tail="",
) -> Measurement:
    return Measurement(
        findings=findings or {},
        failed_tests=frozenset(failed),
        suite_status=status,
        output_tail=tail,
    )


def test_no_regression_when_nothing_is_new() -> None:
    assert (
        find_regressions(
            measurement(failed=["a"]),
            measurement(failed=["a"]),
        )
        == []
    )


def test_new_failures_are_reported_with_the_output_tail() -> None:
    problems = find_regressions(
        measurement(),
        measurement(failed=["t::x"], tail="boom"),
    )

    assert "t::x" in problems[0]
    assert "boom" in problems[0]


def test_new_static_findings_are_regressions() -> None:
    key = ("ruff", "F821: Undefined name", "a.py")

    assert (
        find_regressions(
            measurement({key: 1}),
            measurement({key: 1}),
        )
        == []
    )

    assert find_regressions(
        measurement({key: 1}),
        measurement({key: 2}),
    )


def test_a_timeout_after_a_clean_baseline_is_a_regression() -> None:
    after = measurement(status=SuiteStatus.TIMED_OUT)

    assert find_regressions(measurement(), after)


def test_failed_test_ids_drop_the_message() -> None:
    suite = SuiteResult(
        SuiteStatus.FAILED,
        failures=(
            "FAILED t.py::a - boom",
            "ERROR t.py::b - bad import",
        ),
    )

    assert failed_test_ids(suite) == {"t.py::a", "t.py::b"}


async def test_unverified_when_baseline_suite_has_error(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})

    engine, _ = setup(
        tmp_path,
        llm,
        [SuiteResult(SuiteStatus.ERROR)],
    )

    proposal = await run(engine)

    assert proposal.status is FixStatus.UNVERIFIED
    assert any("baseline validation failed" in note for note in proposal.notes)


async def test_unverified_when_baseline_suite_times_out(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})

    engine, _ = setup(
        tmp_path,
        llm,
        [SuiteResult(SuiteStatus.TIMED_OUT)],
    )

    proposal = await run(engine)

    assert proposal.status is FixStatus.UNVERIFIED
    assert any("timed_out" in note for note in proposal.notes)


async def test_unverified_when_post_fix_suite_has_error(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})

    engine, _ = setup(
        tmp_path,
        llm,
        [PASSED, SuiteResult(SuiteStatus.ERROR)],
    )

    proposal = await run(engine)

    assert proposal.status is FixStatus.UNVERIFIED
    assert any("post-fix validation failed" in note for note in proposal.notes)


async def test_unverified_when_no_tests_and_no_analyzers(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})

    engine, _ = setup(tmp_path, llm, [NO_TESTS])

    proposal = await run(engine)

    assert proposal.status is FixStatus.UNVERIFIED


async def test_verified_with_static_analysis_when_no_tests_exist(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})
    analyzer = FakeAnalyzer()

    engine, _ = setup(
        tmp_path,
        llm,
        [NO_TESTS, NO_TESTS],
        analyzers=[analyzer],
    )

    proposal = await run(engine)

    assert proposal.status is FixStatus.VERIFIED
    assert analyzer.calls == 2
    assert any("static analysis only" in note for note in proposal.notes)


async def test_unverified_when_analyzer_fails(
    tmp_path: Path,
) -> None:
    llm = FakeLLM({"fixer": edit_out(OLD_LINE, NEW_LINE)})
    analyzer = FakeAnalyzer(error="tool crashed")

    engine, _ = setup(
        tmp_path,
        llm,
        analyzers=[analyzer],
    )

    proposal = await run(engine)

    assert proposal.status is FixStatus.UNVERIFIED
    assert any("fake-analyzer failed" in note for note in proposal.notes)


def test_no_tests_after_a_working_baseline_is_a_regression() -> None:
    before = measurement(status=SuiteStatus.PASSED)
    after = measurement(status=SuiteStatus.NO_TESTS)

    problems = find_regressions(before, after)

    assert any("collected no tests" in problem for problem in problems)


def test_fix_settings_reject_invalid_attempt_count() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        FixSettings(max_attempts=0)


def test_apply_rejects_all_edits_for_a_file_atomically() -> None:
    current = {"src/a.py": ORIGINAL}

    fix = FileFix(
        edits=[
            EditOut(old_text=OLD_LINE, new_text=NEW_LINE),
            EditOut(
                old_text="missing line\n",
                new_text="replacement\n",
            ),
        ],
        explanation="Apply two edits",
    )

    proposed, rejections = FixEngine._apply(
        current,
        {"src/a.py": fix},
    )

    assert proposed == current
    assert len(rejections) == 1
    assert "not found" in rejections[0]
