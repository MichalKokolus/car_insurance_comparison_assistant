"""Keyless stub provider — deterministic canned output so the whole flow runs with no API key.

It only fabricates the one thing that has no deterministic source: the policy *extraction*
(`PolicyData`). Comparison and recommendation are computed by real code in `backend.logic`, so the
stub deliberately does not answer those schemas.

The canned policy omits `anniversary_date` and `notice_period_days` on purpose, so the graph's
human-in-the-loop (`validate` -> interrupt) path is exercised in every stub demo.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from backend.schemas import PolicyData

T = TypeVar("T", bound=BaseModel)


class StubProvider:
    name = "stub"

    async def structured(self, system: str, user: str, schema: type[T]) -> T:
        if schema is PolicyData:
            return PolicyData(
                insurer="Allianz - Slovenská poisťovňa",
                vehicle="Škoda Octavia 1.6 TDI (2018)",
                coverage_type="PZP",
                annual_premium=210.0,
                anniversary_date=None,  # intentionally missing -> triggers HITL
                notice_period_days=None,  # intentionally missing -> triggers HITL
                deductible="—",
                glass_cover=False,
                animal_cover=False,
                liability_limit="5,24 mil. € / 1,05 mil. €",
            )  # type: ignore[return-value]
        raise NotImplementedError(
            f"StubProvider has no canned value for {schema.__name__}; this schema is computed "
            "deterministically in backend.logic, not by the LLM."
        )

    async def structured_with_images(self, system, text, images, schema):
        # The stub ignores inputs entirely; delegate to the text path.
        return await self.structured(system, text, schema)

    def chat_model(self):
        raise NotImplementedError(
            "StubProvider has no chat model. Set ANTHROPIC_API_KEY and LLM_PROVIDER=anthropic "
            "to enable the ReAct research agent."
        )
