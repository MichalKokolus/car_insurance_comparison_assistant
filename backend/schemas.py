"""Pydantic v2 schemas — the typed objects the graph passes between nodes, plus API models."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

CoverageType = Literal["PZP", "kasko"]


class PolicyData(BaseModel):
    """Structured details extracted from the user's current policy PDF."""

    insurer: Optional[str] = None
    vehicle: Optional[str] = None
    coverage_type: CoverageType = "PZP"
    annual_premium: Optional[float] = None  # EUR / year
    anniversary_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    deductible: Optional[str] = None
    glass_cover: Optional[bool] = None
    animal_cover: Optional[bool] = None
    liability_limit: Optional[str] = None


class Offer(BaseModel):
    """A single market offer returned by the research step."""

    insurer: str
    product: str
    coverage_type: CoverageType
    annual_premium: float
    deductible: Optional[str] = None
    glass_cover: Optional[bool] = None
    animal_cover: Optional[bool] = None
    liability_limit: Optional[str] = None
    source: Optional[str] = None


class ComparisonRow(BaseModel):
    """One offer normalized against the user's current policy."""

    insurer: str
    product: str
    annual_premium: float
    premium_delta: Optional[float] = None  # offer - current (negative = cheaper)
    glass_cover: Optional[bool] = None
    animal_cover: Optional[bool] = None
    liability_limit: Optional[str] = None
    comparable: bool = True
    notes: Optional[str] = None


class ComparisonTable(BaseModel):
    rows: list[ComparisonRow] = Field(default_factory=list)
    summary: Optional[str] = None


class Recommendation(BaseModel):
    verdict: Literal["switch", "stay"]
    rationale: str
    best_offer: Optional[Offer] = None
    estimated_annual_saving: Optional[float] = None
    cancellation_deadline: Optional[date] = None  # always set by deterministic code, never the LLM
    deadline_note: str = ""


# ---- API models -------------------------------------------------------------


class StartResponse(BaseModel):
    thread_id: str


class ResumeRequest(BaseModel):
    answers: dict
