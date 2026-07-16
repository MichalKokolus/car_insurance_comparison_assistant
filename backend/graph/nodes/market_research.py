"""market_research — the one real agent.

Stub provider: returns the canned offers directly (no model available).
Real provider: runs a ReAct agent over the web_search tool, capped to keep costs bounded, then
folds the (stubbed) search results into Offer objects.
"""

from __future__ import annotations

from backend.data.offers import CANNED_OFFERS
from backend.graph.state import AppState
from backend.services.llm.factory import get_provider
from backend.services.llm.stub_provider import StubProvider

# Per-agent recursion cap ~ a handful of tool calls (each ReAct step ≈ 2 supersteps). This is the
# in-code half of the runaway-cost guardrail (the other half is the account spend limit).
RESEARCH_RECURSION_LIMIT = 12


async def market_research(state: AppState) -> dict:
    provider = get_provider()
    if isinstance(provider, StubProvider):
        return {"market_offers": list(CANNED_OFFERS)}

    offers = await _research_with_agent(provider, state)
    return {"market_offers": offers or list(CANNED_OFFERS)}


async def _research_with_agent(provider, state: AppState) -> list | None:
    from langgraph.prebuilt import create_react_agent

    from backend.graph.tools.search import web_search

    policy = state["policy"]
    agent = create_react_agent(provider.chat_model(), tools=[web_search])
    profile = (
        f"{policy.vehicle or 'unknown vehicle'}, current {policy.coverage_type} premium "
        f"{policy.annual_premium} EUR/yr"
    )
    prompt = (
        "Use web_search to find current Slovak car-insurance offers for this vehicle profile, then "
        f"summarize them. Make at most 5 searches. Profile: {profile}."
    )
    try:
        await agent.ainvoke(
            {"messages": [("user", prompt)]},
            config={"recursion_limit": RESEARCH_RECURSION_LIMIT},
        )
    except Exception:
        return None
    # The tool is stubbed in the PoC, so the authoritative offers come from the fixture.
    return list(CANNED_OFFERS)
