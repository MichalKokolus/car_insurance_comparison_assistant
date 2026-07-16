"""Shared graph state. Nodes read what they need and return partial updates."""

from __future__ import annotations

from typing import Optional, TypedDict

from backend.schemas import ComparisonTable, Offer, PolicyData, Recommendation


class AppState(TypedDict, total=False):
    pdf_text: str
    policy: Optional[PolicyData]
    missing_fields: list[str]
    user_answers: dict
    market_offers: list[Offer]
    comparison: Optional[ComparisonTable]
    recommendation: Optional[Recommendation]
    report: str
