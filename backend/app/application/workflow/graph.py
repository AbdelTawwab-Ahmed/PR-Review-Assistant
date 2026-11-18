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
from app.application.workflow.nodes.static_analysis import make_static_analysis
from app.application.workflow.state import ReviewState

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


def build_analysis_graph(deps: WorkflowDeps):
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
    graph.add_edge("score_risk", END)


    return graph.compile()
