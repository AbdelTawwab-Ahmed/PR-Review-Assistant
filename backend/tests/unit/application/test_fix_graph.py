from app.application.ports.sandbox_port import SandboxError
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.graph import build_analysis_graph
from app.application.workflow.schemas import FindingsOut
from app.domain.entities.fix_proposal import FixProposal
from app.domain.enums import ApprovalDecision, FixStatus, Severity
from tests.fakes import FakeGitHub, FakeLLM, finding_out, make_pr

VERIFIED = FixProposal(FixStatus.VERIFIED, "abc123", summary="done")


class FakeEngine:
    def __init__(self, proposal: FixProposal = VERIFIED, error: Exception | None = None) -> None:
        self.proposal = proposal
        self.error = error
        self.calls: list[tuple] = []

    async def run(self, pr, plan, findings):
        self.calls.append((pr, plan, findings))
        if self.error:
            raise self.error
        return self.proposal


def llm_with(severity: Severity) -> FakeLLM:
    out = FindingsOut(findings=[finding_out("Hardcoded password", severity)])
    return FakeLLM({"reviewer": out})


async def run(engine: FakeEngine, llm: FakeLLM, fix: bool):
    graph = build_analysis_graph(
        WorkflowDeps(github=FakeGitHub(make_pr()), llm=llm, fix_engine=engine)
    )
    return await graph.ainvoke(
        {
            "repo_full_name": "org/repo",
            "pr_number": 1,
            "fix_requested": fix,
            "plan_approval_decision": ApprovalDecision.APPROVE,
        }
    )


async def test_fixes_are_proposed_when_requested() -> None:
    engine = FakeEngine()
    state = await run(engine, llm_with(Severity.HIGH), fix=True)
    assert state["proposal"] is VERIFIED
    (_, plan, findings) = engine.calls[0]
    assert [a.file_path for a in plan.actions] == ["src/a.py"]
    assert findings[0].title == "Hardcoded password"


async def test_analysis_only_runs_do_not_touch_the_fixer() -> None:
    engine = FakeEngine()
    state = await run(engine, llm_with(Severity.HIGH), fix=False)
    assert engine.calls == []
    assert "proposal" not in state


async def test_minor_findings_do_not_start_the_fixer() -> None:
    engine = FakeEngine()
    await run(engine, llm_with(Severity.LOW), fix=True)
    assert engine.calls == []


async def test_engine_failures_become_a_failed_proposal() -> None:
    engine = FakeEngine(error=SandboxError("docker unavailable"))
    state = await run(engine, llm_with(Severity.HIGH), fix=True)
    assert state["proposal"].status is FixStatus.FAILED
    assert "docker unavailable" in state["proposal"].notes[0]
