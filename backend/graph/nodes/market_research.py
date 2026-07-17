"""market_research — the one real agent.

Stub provider: returns the canned offers directly (no model available).
Real provider: runs a ReAct agent over a live DuckDuckGo `web_search` tool (capped to keep costs
bounded), then extracts structured `Offer`s from the agent's findings. If live search yields no
concretely priced offers, falls back to clearly-labelled sample data.
"""

from __future__ import annotations

from backend.data.offers import CANNED_OFFERS, sample_offers
from backend.graph.state import AppState
from backend.schemas import OfferList
from backend.services.llm.factory import get_provider
from backend.services.llm.stub_provider import StubProvider

# Per-agent recursion cap ~ a handful of tool calls (each ReAct step ≈ 2 supersteps). This is the
# in-code half of the runaway-cost guardrail (the other half is the account spend limit).
RESEARCH_RECURSION_LIMIT = 12

_EXTRACT_SYSTEM = (
    "From the web-research notes below, extract concrete Slovak car-insurance offers. "
    "Include an offer only when the insurer name AND an annual premium in EUR are clearly stated. "
    "Do not invent prices or insurers. Return an empty list if nothing is concretely priced."
)


async def market_research(state: AppState) -> dict:
    provider = get_provider()
    if isinstance(provider, StubProvider):
        return {"market_offers": list(CANNED_OFFERS)}

    offers = await _research_with_agent(provider, state)
    if offers:
        return {"market_offers": offers}
    # Live search found nothing concretely priced — fall back to clearly-labelled sample data.
    return {"market_offers": sample_offers()}


async def _research_with_agent(provider, state: AppState) -> list | None:
    from langgraph.prebuilt import create_react_agent

    from backend.graph.tools.search import web_search

    policy = state["policy"]
    profile = f"{policy.vehicle or 'a passenger car'}, coverage type {policy.coverage_type}"
    prompt = (
        "You research Slovak car-insurance offers. Use web_search (at most 5 searches) to find "
        f"current PZP/kasko offers with annual premiums for: {profile}. Then list every concrete "
        "offer you found — insurer, product, annual premium in EUR, and coverage features."
    )
    try:
        agent = create_react_agent(provider.chat_model(), tools=[web_search])
        result = await agent.ainvoke(
            {"messages": [("user", prompt)]},
            config={"recursion_limit": RESEARCH_RECURSION_LIMIT},
        )
        notes = result["messages"][-1].content
        if isinstance(notes, list):
            notes = " ".join(b.get("text", "") for b in notes if isinstance(b, dict))
        extracted: OfferList = await provider.structured(
            _EXTRACT_SYSTEM, str(notes)[:8000], OfferList
        )
        offers = [o for o in extracted.offers if o.insurer and o.annual_premium]
        return offers or None
    except Exception:
        return None
