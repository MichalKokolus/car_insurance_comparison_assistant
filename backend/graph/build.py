"""Graph construction. A fixed pipeline with conditional pausing — not a free-form supervisor."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.graph.nodes.coverage_compare import coverage_compare
from backend.graph.nodes.decision import decision
from backend.graph.nodes.intake import intake
from backend.graph.nodes.market_research import market_research
from backend.graph.nodes.report import report
from backend.graph.nodes.validate import validate
from backend.graph.state import AppState

# Graph-level cost guardrail: a hard ceiling on total super-steps for one run.
RECURSION_LIMIT = 25


def build_graph(checkpointer: Any):
    """Build and compile the graph with the given checkpointer (enables interrupt()/resume)."""
    graph = StateGraph(AppState)

    graph.add_node("intake", intake)
    graph.add_node("validate", validate)
    graph.add_node("market_research", market_research)
    graph.add_node("coverage_compare", coverage_compare)
    graph.add_node("decision", decision)
    graph.add_node("report", report)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "validate")
    graph.add_edge("validate", "market_research")
    graph.add_edge("market_research", "coverage_compare")
    graph.add_edge("coverage_compare", "decision")
    graph.add_edge("decision", "report")
    graph.add_edge("report", END)

    return graph.compile(checkpointer=checkpointer)
