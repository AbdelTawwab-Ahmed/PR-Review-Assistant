from app.application.ports.sandbox_port import SandboxError
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.graph import build_analysis_graph
from app.application.workflow.schemas import FindingsOut
from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity
from tests.fakes import (
    FakeAnalyzer,
    FakeGitHub,
    FakeLLM,
    FakeWorkspaces,
    finding_out,
    make_file,
    make_pr,
)


def static_finding(line: int = 2) -> Finding:
    return Finding(
        FindingCategory.BUG,
        Severity.MEDIUM,
        "F821: Undefined name",
        "d",
        "ruff",
        "src/a.py",
        line,
        line,
    )


async def run(pr, workspaces, analyzers, llm=None):
    graph = build_analysis_graph(
        WorkflowDeps(
            github=FakeGitHub(pr),
            llm=llm or FakeLLM(),
            workspaces=workspaces,
            analyzers=tuple(analyzers),
        )
    )
    return await graph.ainvoke({"repo_full_name": "org/repo", "pr_number": 1})


async def test_static_findings_join_the_llm_findings() -> None:
    llm = FakeLLM({"reviewer": FindingsOut(findings=[finding_out("Off by one")])})
    state = await run(make_pr(), FakeWorkspaces(), [FakeAnalyzer("ruff", [static_finding()])], llm)
    assert {f.source for f in state["final_findings"]} == {"ruff", "reviewer"}


async def test_findings_outside_the_diff_are_dropped() -> None:
    analyzer = FakeAnalyzer("ruff", [static_finding(line=99)])
    state = await run(make_pr(), FakeWorkspaces(), [analyzer])
    assert state["final_findings"] == []


async def test_failed_analyzer_is_reported_in_notes() -> None:
    analyzer = FakeAnalyzer("semgrep", error="timed out")
    state = await run(make_pr(), FakeWorkspaces(), [analyzer])
    assert "semgrep failed: timed out" in state["notes"]


async def test_workspace_failure_does_not_break_the_run() -> None:
    llm = FakeLLM({"reviewer": FindingsOut(findings=[finding_out("Off by one")])})
    workspaces = FakeWorkspaces(fail=SandboxError("docker unavailable"))
    state = await run(make_pr(), workspaces, [FakeAnalyzer("ruff")], llm)
    assert [f.source for f in state["final_findings"]] == ["reviewer"]
    assert any("static analysis skipped" in note for note in state["notes"])


async def test_only_analyzable_files_reach_the_analyzers() -> None:
    analyzer = FakeAnalyzer("ruff")
    pr = make_pr([make_file("src/a.py"), make_file("README.md")])
    await run(pr, FakeWorkspaces(), [analyzer])
    assert analyzer.calls == [["src/a.py"]]


async def test_no_workspace_is_opened_without_analyzable_files() -> None:
    workspaces = FakeWorkspaces()
    await run(make_pr([make_file("README.md")]), workspaces, [FakeAnalyzer("ruff")])
    assert workspaces.opened == []
