"""coverage_compare — normalize market offers to a like-for-like table against the policy."""

from __future__ import annotations

from backend.graph.state import AppState
from backend.logic import build_comparison
from backend.schemas import ComparisonTable
from backend.services.llm.factory import get_provider
from backend.services.llm.stub_provider import StubProvider

_SYSTEM = (
    "You normalize car-insurance offers into a like-for-like comparison against the user's current "
    "policy. Compare premium and coverage dimensions (glass, animal, deductible, liability limit) "
    "and flag any offer that is not directly comparable."
)


async def coverage_compare(state: AppState) -> dict:
    provider = get_provider()
    policy = state["policy"]
    offers = state.get("market_offers") or []

    if isinstance(provider, StubProvider):
        return {"comparison": build_comparison(policy, offers)}

    user = (
        f"Current policy:\n{policy.model_dump_json()}\n\n"
        f"Offers:\n{[o.model_dump() for o in offers]}"
    )
    table = await provider.structured(_SYSTEM, user, ComparisonTable)
    return {"comparison": table}
