"""Deterministic comparison + recommendation logic.

Used directly by the stub path, and available as a fallback for the real-LLM path. Keeping the
business rules here (not in an LLM) makes them testable and predictable.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from backend.schemas import (
    ComparisonRow,
    ComparisonTable,
    Offer,
    PolicyData,
    Recommendation,
)


def build_comparison(policy: PolicyData, offers: list[Offer]) -> ComparisonTable:
    """Normalize each offer against the current policy into a like-for-like table."""
    current = policy.annual_premium
    rows: list[ComparisonRow] = []
    for offer in offers:
        delta = None if current is None else round(offer.annual_premium - current, 2)
        comparable = offer.coverage_type == policy.coverage_type
        rows.append(
            ComparisonRow(
                insurer=offer.insurer,
                product=offer.product,
                annual_premium=offer.annual_premium,
                premium_delta=delta,
                glass_cover=offer.glass_cover,
                animal_cover=offer.animal_cover,
                liability_limit=offer.liability_limit,
                comparable=comparable,
                notes=None if comparable else f"Different coverage type ({offer.coverage_type})",
            )
        )
    rows.sort(key=lambda r: r.annual_premium)
    summary = _comparison_summary(policy, rows)
    return ComparisonTable(rows=rows, summary=summary)


def _comparison_summary(policy: PolicyData, rows: list[ComparisonRow]) -> str:
    if not rows:
        return "No comparable offers found."
    cheapest = rows[0]
    if policy.annual_premium is None:
        return f"Cheapest offer: {cheapest.insurer} at €{cheapest.annual_premium:.0f}/yr."
    return (
        f"Current premium €{policy.annual_premium:.0f}/yr; cheapest offer "
        f"{cheapest.insurer} at €{cheapest.annual_premium:.0f}/yr."
    )


def deadline_note(deadline: Optional[date], today: Optional[date] = None) -> str:
    if deadline is None:
        return "Cancellation deadline unknown — anniversary date or notice period missing."
    today = today or date.today()
    if deadline < today:
        return f"The cancellation window for this renewal has already closed (was {deadline.isoformat()})."
    days_left = (deadline - today).days
    return f"Deliver the cancellation notice by {deadline.isoformat()} ({days_left} days from today)."


def build_recommendation(
    policy: PolicyData,
    comparison: ComparisonTable,
    deadline: Optional[date],
    today: Optional[date] = None,
) -> Recommendation:
    """Pick the cheapest comparable offer and decide switch vs stay on premium."""
    comparable_rows = [r for r in comparison.rows if r.comparable]
    if not comparable_rows or policy.annual_premium is None:
        return Recommendation(
            verdict="stay",
            rationale="Not enough comparable market data to justify switching.",
            cancellation_deadline=deadline,
            deadline_note=deadline_note(deadline, today),
        )

    best_row = min(comparable_rows, key=lambda r: r.annual_premium)
    saving = round(policy.annual_premium - best_row.annual_premium, 2)
    best_offer = Offer(
        insurer=best_row.insurer,
        product=best_row.product,
        coverage_type=policy.coverage_type,
        annual_premium=best_row.annual_premium,
        glass_cover=best_row.glass_cover,
        animal_cover=best_row.animal_cover,
        liability_limit=best_row.liability_limit,
    )

    if saving > 0:
        verdict = "switch"
        rationale = (
            f"{best_offer.insurer} ({best_offer.product}) costs €{best_offer.annual_premium:.0f}/yr "
            f"vs your €{policy.annual_premium:.0f}/yr — an estimated €{saving:.0f}/yr saving."
        )
    else:
        verdict = "stay"
        rationale = (
            "Your current premium is already at or below the cheapest comparable market offer."
        )

    return Recommendation(
        verdict=verdict,
        rationale=rationale,
        best_offer=best_offer,
        estimated_annual_saving=saving if saving > 0 else None,
        cancellation_deadline=deadline,
        deadline_note=deadline_note(deadline, today),
    )
