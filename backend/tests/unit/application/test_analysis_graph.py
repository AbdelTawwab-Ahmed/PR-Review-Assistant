from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.diff_chunks import render_file
from app.application.workflow.graph import build_analysis_graph
from app.application.workflow.schemas import FindingsOut, ImpactOut
from app.domain.enums import FindingCategory, RiskLevel, Severity
from tests.fakes import FakeGitHub, FakeLLM, finding_out, make_file, make_pr


def build(pr, llm, **kwargs):
    return build_analysis_graph(WorkflowDeps(github=FakeGitHub(pr), llm=llm, **kwargs))


async def run(graph):
    return await graph.ainvoke({"repo_full_name": "org/repo", "pr_number": 1})


async def test_full_analysis_merges_findings_and_scores_risk() -> None:
    llm = FakeLLM(
        {
            "reviewer": FindingsOut(findings=[finding_out("Off by one", Severity.MEDIUM)]),
            "security": FindingsOut(
                findings=[
                    finding_out("Hardcoded password", Severity.HIGH, FindingCategory.SECURITY)
                ]
            ),
            "impact": ImpactOut(
                summary="Touches login.",
                affected_components=["auth"],
                breaking_changes=[],
                suggested_checks=["Run auth tests"],
            ),
        }
    )
    state = await run(build(make_pr(), llm))
    assert [f.title for f in state["final_findings"]] == ["Hardcoded password", "Off by one"]
    assert state["impact"].affected_components == ("auth",)
    assert state["risk"].score > 0
    assert {c["purpose"] for c in llm.calls} == {"reviewer", "security", "impact"}


async def test_one_failing_agent_does_not_break_the_run() -> None:
    llm = FakeLLM(
        {"reviewer": FindingsOut(findings=[finding_out("Off by one")])}, failing={"security"}
    )
    state = await run(build(make_pr(), llm))
    assert [f.source for f in state["final_findings"]] == ["reviewer"]
    assert any("security" in note for note in state["notes"])


async def test_each_chunk_is_analyzed_by_both_agents() -> None:
    files = [make_file(f"src/f{i}.py") for i in range(3)]
    one = len(render_file(files[0], 10_000).text)
    llm = FakeLLM()
    await run(build(make_pr(files), llm, chunk_chars=one, max_chunks=10))
    purposes = [c["purpose"] for c in llm.calls]
    assert purposes.count("reviewer") == 3
    assert purposes.count("security") == 3
    assert purposes.count("impact") == 1


async def test_pr_without_reviewable_files_skips_the_llm() -> None:
    llm = FakeLLM()
    pr = make_pr([make_file("poetry.lock"), make_file("logo.png")])
    state = await run(build(pr, llm))
    assert llm.calls == []
    assert state["final_findings"] == []
    assert state["risk"].level is RiskLevel.LOW


async def test_skipped_files_are_reported_in_notes() -> None:
    files = [make_file(f"src/f{i}.py") for i in range(3)]
    one = len(render_file(files[0], 10_000).text)
    state = await run(build(make_pr(files), FakeLLM(), chunk_chars=one, max_chunks=1))
    assert any("not analyzed" in note for note in state["notes"])