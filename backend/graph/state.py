"""Shared graph state. Nodes read what they need and return partial updates."""

from __future__ import annotations

from typing import Optional, TypedDict

from backend.schemas import ComparisonTable, Offer, PolicyData, Recommendation


class AppState(TypedDict, total=False):
    pdf_text: str
    pdf_b64: str  # raw PDF (base64) — enables the vision fallback for scanned PDFs
    policy: Optional[PolicyData]
    missing_fields: list[str]
    user_answers: dict
    market_offers: list[Offer]
    research_log: list[dict]  # queries market_research ran + the URLs/snippets each returned
    comparison: Optional[ComparisonTable]
    recommendation: Optional[Recommendation]
    report: str
