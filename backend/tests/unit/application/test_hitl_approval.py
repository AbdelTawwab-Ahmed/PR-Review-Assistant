import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.application.ports.github_port import FileUpdate
from app.application.use_cases.approve_run import ApproveRun
from app.application.use_cases.get_run_status import GetRunStatus
from app.application.use_cases.publish_fix import PublishFix
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.graph import build_analysis_graph
from app.application.workflow.schemas import FindingsOut
from app.domain.entities.fix_proposal import FileChange, FixProposal
from app.domain.enums import ApprovalDecision, FixStatus, RunStatus, Severity
from app.domain.exceptions import RunNotFoundError
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
        {
            "repo_full_name": "org/repo",
            "pr_number": 1,
            "fix_requested": True,
            "plan_approval_decision": ApprovalDecision.APPROVE,
        },
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
        {
            "repo_full_name": "org/repo",
            "pr_number": 1,
            "fix_requested": True,
            "plan_approval_decision": ApprovalDecision.APPROVE,
        },
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
        {
            "repo_full_name": "org/repo",
            "pr_number": 1,
            "fix_requested": True,
            "plan_approval_decision": ApprovalDecision.APPROVE,
        },
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
        {
            "repo_full_name": "org/repo",
            "pr_number": 1,
            "fix_requested": True,
            "plan_approval_decision": ApprovalDecision.APPROVE,
        },
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
    with pytest.raises(RunNotFoundError):
        await approve_use_case.execute("unknown-run", ApprovalDecision.APPROVE)


async def test_stage_1_plan_approval_interrupt() -> None:
    pr = make_pr()
    gh = FakePublisherGitHub(pr)
    engine = FakeEngine(PUBLISHABLE_PROPOSAL)
    checkpointer = MemorySaver()
    graph = make_graph(gh, engine, checkpointer)

    config = {"configurable": {"thread_id": "run-test-stage1"}}
    await graph.ainvoke(
        {"repo_full_name": "org/repo", "pr_number": 1, "fix_requested": True},
        config=config,
    )

    state_snapshot = await graph.aget_state(config)
    assert len(state_snapshot.tasks) > 0
    interrupts = [i.value for t in state_snapshot.tasks for i in t.interrupts]
    assert len(interrupts) == 1
    assert interrupts[0]["status"] == "awaiting_plan_approval"


async def test_unverified_fix_reaches_gate2_and_publishes_when_allowed() -> None:
    pr = make_pr()
    gh = FakePublisherGitHub(pr)
    unverified_proposal = FixProposal(
        status=FixStatus.UNVERIFIED,
        base_sha="abc123",
        changes=(FileChange("src/a.py", "old", "new"),),
        summary="syntax-checked fix without sandbox",
    )
    engine = FakeEngine(unverified_proposal)
    checkpointer = MemorySaver()
    graph = build_analysis_graph(
        WorkflowDeps(
            github=gh,
            llm=llm_with_finding(),
            fix_engine=engine,
            publisher=PublishFix(gh),
            allow_unverified_fixes=True,
        ),
        checkpointer=checkpointer,
    )

    from app.domain.entities.review_run import ReviewRun
    from app.infrastructure.persistence.repositories import InMemoryReviewRunRepository

    repo = InMemoryReviewRunRepository()
    await repo.save(
        ReviewRun(
            id="run-unverified-1",
            repo_full_name="org/repo",
            pr_number=1,
            head_sha="abc123",
            status=RunStatus.AWAITING_PLAN_APPROVAL,
        )
    )

    approve = ApproveRun(graph, repo)
    # Simulate server restart where MemorySaver is empty, recovering from repository:
    gate1 = await approve.execute("run-unverified-1", ApprovalDecision.APPROVE)
    assert gate1.status == "interrupted"

    saved_after_gate1 = await repo.get_by_id("run-unverified-1")
    assert saved_after_gate1 is not None
    assert saved_after_gate1.status == RunStatus.AWAITING_APPROVAL

    # Approve Gate 2 -> should publish PR!
    gate2 = await approve.execute("run-unverified-1", ApprovalDecision.APPROVE)
    assert gate2.status == "completed"
    assert gate2.published_pr_url == "https://github.com/org/repo/pull/99"
    assert len(gh.opened_prs) == 1

    saved_after_gate2 = await repo.get_by_id("run-unverified-1")
    assert saved_after_gate2 is not None
    assert saved_after_gate2.status == RunStatus.READY_TO_MERGE
