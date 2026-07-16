"""decision — deterministic deadline math + a switch/stay verdict.

The cancellation deadline is ALWAYS computed in code and written onto the recommendation, even when
an LLM produces the surrounding reasoning. Dates are exactly what LLMs get wrong.
"""

from __future__ import annotations

from backend.deadlines import compute_cancellation_deadline
from backend.graph.state import AppState
from backend.logic import build_recommendation, deadline_note
from backend.schemas import Recommendation
from backend.services.llm.factory import get_provider
from backend.services.llm.stub_provider import StubProvider

_SYSTEM = (
    "You advise whether to switch car insurer or stay, based on a like-for-like comparison table. "
    "Give a concise, factual rationale. Do not compute any dates."
)


async def decision(state: AppState) -> dict:
    provider = get_provider()
    policy = state["policy"]
    comparison = state["comparison"]

    deadline = compute_cancellation_deadline(policy.anniversary_date, policy.notice_period_days)

    if isinstance(provider, StubProvider):
        return {"recommendation": build_recommendation(policy, comparison, deadline)}

    user = (
        f"Current policy:\n{policy.model_dump_json()}\n\n"
        f"Comparison:\n{comparison.model_dump_json()}"
    )
    rec: Recommendation = await provider.structured(_SYSTEM, user, Recommendation)
    # Deterministic override — never trust the model's dates.
    rec.cancellation_deadline = deadline
    rec.deadline_note = deadline_note(deadline)
    return {"recommendation": rec}
