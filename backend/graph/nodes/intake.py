"""intake — PDF text -> structured PolicyData via a single structured-output LLM call."""

from __future__ import annotations

from backend.graph.state import AppState
from backend.schemas import PolicyData
from backend.services.llm.factory import get_provider

_SYSTEM = (
    "You extract structured car-insurance policy data from the raw text of a Slovak policy PDF. "
    "Fill only fields you are confident about; leave anything uncertain as null. "
    "coverage_type is 'PZP' (mandatory liability) or 'kasko' (comprehensive)."
)


async def intake(state: AppState) -> dict:
    provider = get_provider()
    text = (state.get("pdf_text") or "").strip() or "(no text could be extracted from the PDF)"
    policy = await provider.structured(_SYSTEM, f"Policy document text:\n\n{text[:6000]}", PolicyData)
    return {"policy": policy}
