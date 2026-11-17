from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.application.workflow.agents.impact import ImpactAgent
from app.application.workflow.agents.reviewer import ReviewerAgent
from app.application.workflow.agents.security import SecurityAgent
from app.application.workflow.deps import WorkflowDeps
from app.application.workflow.nodes.aggregate_findings import aggregate_findings
from app.application.workflow.nodes.analyze_chunk import make_analyze_chunk
from app.application.workflow.nodes.fetch_context import make_fetch_context
from app.application.workflow.nodes.impact_analysis import make_impact_analysis
from app.application.workflow.nodes.plan_analysis import make_plan_analysis
from app.application.workflow.nodes.score_risk import score_risk
from app.application.workflow.state import ReviewState

CHUNK_AGENTS = ("reviewer", "security")


def fan_out(state: ReviewState) -> list[Send | str]:
    """Dynamic fan-out: every chunk goes to every agent, plus one impact analysis."""
    chunks = state.get("chunks", [])
    if not chunks:
        return ["aggregate_findings"]
    pr = state["pr"]
    sends: list[Send | str] = [
        Send("analyze_chunk", {"agent": name, "pr": pr, "chunk": chunk})
        for chunk in chunks
        for name in CHUNK_AGENTS
    ]
    sends.append(Send("impact_analysis", {"pr": pr, "chunk": chunks[0]}))
    return sends


def build_analysis_graph(deps: WorkflowDeps):
    chunk_agents = {"reviewer": ReviewerAgent(deps.llm), "security": SecurityAgent(deps.llm)}

    graph = StateGraph(ReviewState)
    graph.add_node("fetch_context", make_fetch_context(deps.github))
    graph.add_node("plan_analysis", make_plan_analysis(deps.chunk_chars, deps.max_chunks))
    graph.add_node("analyze_chunk", make_analyze_chunk(chunk_agents))
    graph.add_node("impact_analysis", make_impact_analysis(ImpactAgent(deps.llm)))
    graph.add_node("aggregate_findings", aggregate_findings)
    graph.add_node("score_risk", score_risk)

    graph.add_edge(START, "fetch_context")
    graph.add_edge("fetch_context", "plan_analysis")
    graph.add_conditional_edges(
        "plan_analysis", fan_out, ["analyze_chunk", "impact_analysis", "aggregate_findings"]
    )
    graph.add_edge("analyze_chunk", "aggregate_findings")
    graph.add_edge("impact_analysis", "aggregate_findings")
    graph.add_edge("aggregate_findings", "score_risk")
    graph.add_edge("score_risk", END)
    return graph.compile()