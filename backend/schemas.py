"""Pydantic v2 schemas — the typed objects the graph passes between nodes, plus API models."""

from __future__ import annotations

from datetime import date
from typing import Any, ClassVar, Literal, Optional

from pydantic import BaseModel, Field, field_validator

CoverageType = Literal["PZP", "kasko"]

# Placeholder strings LLMs emit for "I couldn't find this" instead of null.
_SENTINELS = {
    "",
    "-",
    "—",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "unknown",
    "<unknown>",
    "not specified",
    "not available",
    "not found",
}


class _LLMExtract(BaseModel):
    """Base for schemas the LLM fills.

    Structured-output models sometimes return a placeholder string like ``'<UNKNOWN>'`` for a
    field they can't determine, which then fails type validation on a typed field (float/date/
    int/bool). Normalize those to None (or a per-field fallback for non-nullable fields) *before*
    validation, so an unfound value flows into the human-in-the-loop step instead of crashing.
    """

    _NON_NULLABLE_DEFAULTS: ClassVar[dict[str, Any]] = {}

    @field_validator("*", mode="before")
    @classmethod
    def _nullify_sentinels(cls, value: Any, info: Any) -> Any:
        if isinstance(value, str) and value.strip().lower() in _SENTINELS:
            return cls._NON_NULLABLE_DEFAULTS.get(info.field_name)
        return value


class PolicyData(_LLMExtract):
    """Structured details extracted from the user's current policy PDF."""

    # coverage_type can't be None (it's a required enum with a default), so a sentinel falls back.
    _NON_NULLABLE_DEFAULTS: ClassVar[dict[str, Any]] = {"coverage_type": "PZP"}

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


class Offer(_LLMExtract):
    """A single market offer returned by the research step."""

    _NON_NULLABLE_DEFAULTS: ClassVar[dict[str, Any]] = {"coverage_type": "PZP"}

    insurer: str
    product: str
    coverage_type: CoverageType
    annual_premium: float
    deductible: Optional[str] = None
    glass_cover: Optional[bool] = None
    animal_cover: Optional[bool] = None
    liability_limit: Optional[str] = None
    source: Optional[str] = None


class OfferList(_LLMExtract):
    """Wrapper so the LLM can return a list of offers as structured output."""

    offers: list[Offer] = Field(default_factory=list)


class ComparisonRow(_LLMExtract):
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


class ComparisonTable(_LLMExtract):
    rows: list[ComparisonRow] = Field(default_factory=list)
    summary: Optional[str] = None


class Recommendation(_LLMExtract):
    # verdict/rationale can't be None; fall back if the model returns a placeholder.
    _NON_NULLABLE_DEFAULTS: ClassVar[dict[str, Any]] = {"verdict": "stay", "rationale": ""}

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
