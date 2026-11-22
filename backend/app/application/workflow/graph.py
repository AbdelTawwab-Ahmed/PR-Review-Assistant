from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.application.workflow.agents.impact import ImpactAgent
from app.application.workflow.agents.reviewer import ReviewerAgent
from app.application.workflow.agents.security import SecurityAgent
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.nodes.aggregate_findings import aggregate_findings
from app.application.workflow.nodes.analyze_chunk import make_analyze_chunk
from app.application.workflow.nodes.apply_fixes import make_apply_fixes
from app.application.workflow.nodes.fetch_context import make_fetch_context
from app.application.workflow.nodes.hitl_approval import make_hitl_approval
from app.application.workflow.nodes.hitl_plan_approval import make_hitl_plan_approval
from app.application.workflow.nodes.impact_analysis import make_impact_analysis
from app.application.workflow.nodes.plan_analysis import make_plan_analysis
from app.application.workflow.nodes.plan_fixes import make_plan_fixes
from app.application.workflow.nodes.score_risk import score_risk
from app.application.workflow.nodes.static_analysis import make_static_analysis
from app.application.workflow.nodes.update_pr import make_update_pr
from app.application.workflow.state import ReviewState
from app.domain.enums import ApprovalDecision

CHUNK_AGENTS = ("reviewer", "security")


def make_fan_out(static_enabled: bool):
    def fan_out(state: ReviewState) -> list[Send | str]:
        """LLM agents per chunk, one impact analysis, and the sandbox tools, all in parallel."""
        pr = state["pr"]
        chunks = state.get("chunks", [])
        sends: list[Send | str] = []
        if chunks:
            sends.extend(
                Send("analyze_chunk", {"agent": name, "pr": pr, "chunk": chunk})
                for chunk in chunks
                for name in CHUNK_AGENTS
            )
            sends.append(Send("impact_analysis", {"pr": pr, "chunk": chunks[0]}))
        if static_enabled:
            sends.append(Send("static_analysis", {"pr": pr}))
        return sends or ["aggregate_findings"]

    return fan_out


def after_risk(state: ReviewState) -> str:
    """If issues are detected, pause at Stage 1 HITL for human remediation authorization.
    If repository is clean with no issues, terminate successfully."""
    findings = state.get("final_findings", [])
    if not findings:
        return END
    if state.get("plan_approval_decision") == ApprovalDecision.APPROVE:
        return "plan_fixes"
    return "hitl_plan_approval" if state.get("fix_requested", True) else END


def after_plan_approval(state: ReviewState) -> str:
    """Stage 1 Gate: Proceed to remediation agents only if human explicitly authorized."""
    decision = state.get("plan_approval_decision")
    if decision == ApprovalDecision.APPROVE:
        return "plan_fixes"
    return END


def after_plan(state: ReviewState) -> str:
    plan = state.get("fix_plan")
    return "apply_fixes" if plan is not None and not plan.is_empty else END


def after_apply_fixes(state: ReviewState) -> str:
    proposal = state.get("proposal")
    if proposal is not None and proposal.publishable:
        return "hitl_approval"
    return END


def after_hitl(state: ReviewState) -> str:
    decision = state.get("approval_decision")
    if decision == ApprovalDecision.APPROVE:
        return "update_pr"
    if decision == ApprovalDecision.REQUEST_CHANGES:
        return "plan_fixes"
    return END


def build_analysis_graph(deps: WorkflowDeps, checkpointer: Any = None):
    chunk_agents = {"reviewer": ReviewerAgent(deps.llm), "security": SecurityAgent(deps.llm)}
    destinations = ["analyze_chunk", "impact_analysis", "aggregate_findings"]

    graph = StateGraph(ReviewState)
    graph.add_node("fetch_context", make_fetch_context(deps.github))
    graph.add_node("plan_analysis", make_plan_analysis(deps.chunk_chars, deps.max_chunks))
    graph.add_node("analyze_chunk", make_analyze_chunk(chunk_agents))
    graph.add_node("impact_analysis", make_impact_analysis(ImpactAgent(deps.llm)))
    graph.add_node("aggregate_findings", aggregate_findings)
    graph.add_node("score_risk", score_risk)

    if deps.static_analysis_enabled:
        graph.add_node(
            "static_analysis",
            make_static_analysis(deps.workspaces, deps.analyzers, deps.max_analyzed_files),
        )
        graph.add_edge("static_analysis", "aggregate_findings")
        destinations.append("static_analysis")

    graph.add_edge(START, "fetch_context")
    graph.add_edge("fetch_context", "plan_analysis")
    graph.add_conditional_edges(
        "plan_analysis", make_fan_out(deps.static_analysis_enabled), destinations
    )
    graph.add_edge("analyze_chunk", "aggregate_findings")
    graph.add_edge("impact_analysis", "aggregate_findings")
    graph.add_edge("aggregate_findings", "score_risk")

    if deps.fix_engine is not None:
        graph.add_node("hitl_plan_approval", make_hitl_plan_approval())
        graph.add_node("plan_fixes", make_plan_fixes(deps.fix_min_severity, deps.fix_max_files))
        graph.add_node("apply_fixes", make_apply_fixes(deps.fix_engine))
        graph.add_node("hitl_approval", make_hitl_approval())
        graph.add_node("update_pr", make_update_pr(deps.publisher))

        graph.add_conditional_edges(
            "score_risk", after_risk, ["hitl_plan_approval", "plan_fixes", END]
        )
        graph.add_conditional_edges("hitl_plan_approval", after_plan_approval, ["plan_fixes", END])
        graph.add_conditional_edges("plan_fixes", after_plan, ["apply_fixes", END])
        graph.add_conditional_edges("apply_fixes", after_apply_fixes, ["hitl_approval", END])
        graph.add_conditional_edges("hitl_approval", after_hitl, ["update_pr", "plan_fixes", END])
        graph.add_edge("update_pr", END)
    else:
        graph.add_edge("score_risk", END)
    return graph.compile(checkpointer=checkpointer)
