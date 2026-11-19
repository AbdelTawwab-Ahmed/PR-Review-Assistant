from pathlib import Path

from app.application.ports.sandbox_port import ExecResult, Workspace
from app.application.ports.validation_port import SuiteStatus
from app.infrastructure.sandbox.pytest_runner import PytestRunner
from tests.fakes import FakeSandbox

OK = ExecResult(0, "", "")


def make_workspace(tmp_path: Path, files: dict[str, str]) -> Workspace:
    source = tmp_path / "src"
    source.mkdir()
    for name, content in files.items():
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
    return Workspace(source, tmp_path / "deps")


async def test_passing_suite_installs_deps_then_runs_offline(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path, {"requirements.txt": "requests>=2.0\n"})
    sandbox = FakeSandbox([OK, ExecResult(0, "..........\n10 passed in 0.50s\n", "")])
    result = await PytestRunner(sandbox).run(ws)

    assert result.status is SuiteStatus.PASSED
    assert result.passed == 10

    install, tests = sandbox.calls
    assert install["install_mode"] is True
    assert "--only-binary=:all:" in install["command"]
    assert "requests>=2.0" in install["command"]
    assert tests["install_mode"] is False
    assert tests["env"]["PYTHONPATH"].startswith("/deps")


async def test_failures_are_listed(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path, {"requirements.txt": "pytest\n"})
    output = "FAILED tests/test_a.py::test_x - assert 1 == 2\n1 failed, 3 passed in 0.2s\n"
    sandbox = FakeSandbox([OK, ExecResult(1, output, "")])

    result = await PytestRunner(sandbox).run(ws)

    assert result.status is SuiteStatus.FAILED
    assert (result.failed, result.passed) == (1, 3)
    assert result.failures == ("FAILED tests/test_a.py::test_x - assert 1 == 2",)


async def test_no_tests_collected(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path, {})
    sandbox = FakeSandbox([ExecResult(5, "no tests ran in 0.01s", "")])

    result = await PytestRunner(sandbox).run(ws)

    assert result.status is SuiteStatus.NO_TESTS


async def test_timeout(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path, {})
    sandbox = FakeSandbox([ExecResult(-1, "", "", timed_out=True)])

    result = await PytestRunner(sandbox).run(ws)

    assert result.status is SuiteStatus.TIMED_OUT


async def test_failed_install_is_reported_and_status_is_error(
    tmp_path: Path,
) -> None:
    ws = make_workspace(tmp_path, {"requirements.txt": "pkg-without-wheel\n"})
    sandbox = FakeSandbox(
        [
            ExecResult(1, "", "no matching distribution"),
            ExecResult(0, "1 passed in 0.1s\n", ""),
        ]
    )

    result = await PytestRunner(sandbox).run(ws)

    assert result.status is SuiteStatus.ERROR
    assert result.passed == 1
    assert any("dependency installation failed" in note for note in result.notes)
    assert any("dependency installation failed" in error for error in result.validation_errors)
    assert len(sandbox.calls) == 2


async def test_failed_install_and_failed_tests_still_return_error(
    tmp_path: Path,
) -> None:
    ws = make_workspace(tmp_path, {"requirements.txt": "pkg-without-wheel\n"})
    output = "FAILED tests/test_a.py::test_x - assert 1 == 2\n1 failed, 2 passed in 0.2s\n"
    sandbox = FakeSandbox(
        [
            ExecResult(1, "", "no matching distribution"),
            ExecResult(1, output, ""),
        ]
    )

    result = await PytestRunner(sandbox).run(ws)

    assert result.status is SuiteStatus.ERROR
    assert result.failed == 1
    assert result.passed == 2
    assert result.failures == ("FAILED tests/test_a.py::test_x - assert 1 == 2",)


async def test_no_dependency_list_skips_the_install_step(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path, {"setup.cfg": ""})
    sandbox = FakeSandbox([ExecResult(0, "1 passed in 0.1s", "")])

    result = await PytestRunner(sandbox).run(ws)

    assert len(sandbox.calls) == 1
    assert "dependency" in result.notes[0]


async def test_monorepo_project_folder_is_used(tmp_path: Path) -> None:
    ws = make_workspace(
        tmp_path,
        {"backend/pyproject.toml": '[project]\nname = "x"\n'},
    )
    sandbox = FakeSandbox([ExecResult(0, "1 passed in 0.1s", "")])

    await PytestRunner(sandbox).run(ws)

    call = sandbox.calls[-1]
    assert call["workdir"] == "backend"
    assert "/workspace/backend/src" in call["env"]["PYTHONPATH"]
