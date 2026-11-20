from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.application.ports.github_port import FileUpdate
from app.application.use_cases.approve_run import ApproveRun
from app.application.use_cases.get_run_status import GetRunStatus
from app.application.use_cases.publish_fix import PublishFix
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.graph import build_analysis_graph
from app.application.workflow.schemas import FindingsOut
from app.domain.entities.fix_proposal import FileChange, FixProposal
from app.domain.enums import ApprovalDecision, FixStatus, RunStatus, Severity
from app.domain.exceptions import RunNotAwaitingApprovalError, RunNotFoundError
from tests.fakes import FakeGitHub, FakeLLM, finding_out, make_pr

PUBLISHABLE_PROPOSAL = FixProposal(
    status=FixStatus.VERIFIED,
    base_sha="abc123",
    changes=(FileChange("src/a.py", "old", "new"),),
    summary="fixed security vulnerability",
)


class FakePublisherGitHub(FakeGitHub):
    def __init__(self, pr) -> None:
        super().__init__(pr)
        self.committed_files: list[tuple[str, str, list[FileUpdate]]] = []
        self.opened_prs: list[dict[str, str]] = []

    async def commit_files_to_new_branch(
        self, repo_full_name: str, base_sha: str, branch: str, message: str, files: list[FileUpdate]
    ) -> str:
        self.committed_files.append((repo_full_name, branch, files))
        return "commit_sha_123"

    async def open_pull_request(
        self, repo_full_name: str, head: str, base: str, title: str, body: str
    ) -> str:
        url = f"https://github.com/{repo_full_name}/pull/99"
        self.opened_prs.append({"head": head, "base": base, "title": title, "url": url})
        return url


class FakeEngine:
    def __init__(self, proposal: FixProposal = PUBLISHABLE_PROPOSAL) -> None:
        self.proposal = proposal
        self.calls: list[tuple] = []

    async def run(self, pr, plan, findings):
        self.calls.append((pr, plan, findings))
        return self.proposal


def llm_with_finding() -> FakeLLM:
    out = FindingsOut(findings=[finding_out("SQL Injection", Severity.HIGH)])
    return FakeLLM({"reviewer": out})


def make_graph(github: FakeGitHub, engine: FakeEngine, checkpointer: MemorySaver):
    publisher = PublishFix(github)
    deps = WorkflowDeps(
        github=github,
        llm=llm_with_finding(),
        fix_engine=engine,
        publisher=publisher,
    )
    return build_analysis_graph(deps, checkpointer=checkpointer)


async def test_graph_interrupts_when_proposal_is_publishable() -> None:
    pr = make_pr()
    gh = FakePublisherGitHub(pr)
    engine = FakeEngine(PUBLISHABLE_PROPOSAL)
    checkpointer = MemorySaver()
    graph = make_graph(gh, engine, checkpointer)

    config = {"configurable": {"thread_id": "run-test-1"}}
    state = await graph.ainvoke(
        {"repo_full_name": "org/repo", "pr_number": 1, "fix_requested": True},
        config=config,
    )

    # State paused at hitl_approval
    assert "proposal" in state
    assert state["proposal"].publishable
    # Notice it has not published yet:
    assert gh.opened_prs == []

    # Check task interrupt details
    state_snapshot = await graph.aget_state(config)
    assert len(state_snapshot.tasks) > 0
    interrupts = [i.value for t in state_snapshot.tasks for i in t.interrupts]
    assert len(interrupts) == 1
    assert interrupts[0]["status"] == "awaiting_approval"
    assert interrupts[0]["proposal_summary"] == "fixed security vulnerability"


async def test_approve_run_resumes_and_publishes_fix() -> None:
    pr = make_pr()
    gh = FakePublisherGitHub(pr)
    engine = FakeEngine(PUBLISHABLE_PROPOSAL)
    checkpointer = MemorySaver()
    graph = make_graph(gh, engine, checkpointer)

    config = {"configurable": {"thread_id": "run-test-2"}}
    await graph.ainvoke(
        {"repo_full_name": "org/repo", "pr_number": 1, "fix_requested": True},
        config=config,
    )

    approve_use_case = ApproveRun(graph)
    result = await approve_use_case.execute(
        run_id="run-test-2",
        decision=ApprovalDecision.APPROVE,
    )

    assert result.decision == ApprovalDecision.APPROVE
    assert result.status == "completed"
    assert result.published_pr_url == "https://github.com/org/repo/pull/99"
    assert len(gh.opened_prs) == 1


async def test_reject_run_ends_without_publishing() -> None:
    pr = make_pr()
    gh = FakePublisherGitHub(pr)
    engine = FakeEngine(PUBLISHABLE_PROPOSAL)
    checkpointer = MemorySaver()
    graph = make_graph(gh, engine, checkpointer)

    config = {"configurable": {"thread_id": "run-test-3"}}
    await graph.ainvoke(
        {"repo_full_name": "org/repo", "pr_number": 1, "fix_requested": True},
        config=config,
    )

    approve_use_case = ApproveRun(graph)
    result = await approve_use_case.execute(
        run_id="run-test-3",
        decision=ApprovalDecision.REJECT,
    )

    assert result.decision == ApprovalDecision.REJECT
    assert result.published_pr_url is None
    assert gh.opened_prs == []


async def test_get_run_status_use_case() -> None:
    pr = make_pr()
    gh = FakePublisherGitHub(pr)
    engine = FakeEngine(PUBLISHABLE_PROPOSAL)
    checkpointer = MemorySaver()
    graph = make_graph(gh, engine, checkpointer)

    config = {"configurable": {"thread_id": "run-test-4"}}
    await graph.ainvoke(
        {"repo_full_name": "org/repo", "pr_number": 1, "fix_requested": True},
        config=config,
    )

    status_use_case = GetRunStatus(graph)
    status_result = await status_use_case.execute("run-test-4")

    assert status_result.status == RunStatus.AWAITING_APPROVAL
    assert status_result.findings_count == 1
    assert status_result.proposal is not None
    assert status_result.interrupt_payload is not None


async def test_approve_run_unknown_thread_raises_not_found() -> None:
    checkpointer = MemorySaver()
    graph = make_graph(FakeGitHub(make_pr()), FakeEngine(), checkpointer)

    approve_use_case = ApproveRun(graph)
    try:
        await approve_use_case.execute("unknown-run", ApprovalDecision.APPROVE)
        assert False, "Expected RunNotFoundError"
    except RunNotFoundError:
        pass
