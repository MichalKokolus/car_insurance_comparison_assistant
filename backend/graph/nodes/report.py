"""report — assemble the final markdown report from state. Pure Python, no LLM."""

from __future__ import annotations

from backend.graph.state import AppState
from backend.schemas import ComparisonTable, PolicyData, Recommendation


def _policy_section(policy: PolicyData) -> str:
    anniversary = policy.anniversary_date.isoformat() if policy.anniversary_date else "—"
    premium = f"€{policy.annual_premium:.0f}/yr" if policy.annual_premium is not None else "—"
    return (
        "## Your current policy\n"
        f"- **Insurer:** {policy.insurer or '—'}\n"
        f"- **Vehicle:** {policy.vehicle or '—'}\n"
        f"- **Coverage:** {policy.coverage_type}\n"
        f"- **Premium:** {premium}\n"
        f"- **Anniversary:** {anniversary}\n"
        f"- **Notice period:** {policy.notice_period_days or '—'} days\n"
    )


def _comparison_section(comparison: ComparisonTable) -> str:
    lines = [
        "## Market comparison",
        "",
        "| Insurer | Product | Premium | Δ vs current | Glass | Animal | Comparable |",
        "|---|---|---:|---:|:--:|:--:|:--:|",
    ]
    for row in comparison.rows:
        delta = "—" if row.premium_delta is None else f"€{row.premium_delta:+.0f}"
        glass = "✓" if row.glass_cover else "✗"
        animal = "✓" if row.animal_cover else "✗"
        comp = "✓" if row.comparable else "✗"
        lines.append(
            f"| {row.insurer} | {row.product} | €{row.annual_premium:.0f} | {delta} "
            f"| {glass} | {animal} | {comp} |"
        )
    if comparison.summary:
        lines += ["", f"_{comparison.summary}_"]
    return "\n".join(lines)


def _recommendation_section(rec: Recommendation) -> str:
    saving = (
        f"€{rec.estimated_annual_saving:.0f}/yr"
        if rec.estimated_annual_saving is not None
        else "—"
    )
    best = (
        f"{rec.best_offer.insurer} ({rec.best_offer.product})" if rec.best_offer else "—"
    )
    return (
        "## Recommendation\n"
        f"- **Verdict:** {rec.verdict.upper()}\n"
        f"- **Best offer:** {best}\n"
        f"- **Estimated saving:** {saving}\n"
        f"- **Rationale:** {rec.rationale}\n\n"
        "## Cancellation deadline\n"
        f"- **Deadline:** {rec.cancellation_deadline.isoformat() if rec.cancellation_deadline else '—'}\n"
        f"- {rec.deadline_note}\n"
    )


async def report(state: AppState) -> dict:
    policy = state["policy"]
    comparison = state["comparison"]
    rec = state["recommendation"]

    markdown = "\n\n".join(
        [
            "# Car insurance comparison report",
            _policy_section(policy),
            _comparison_section(comparison),
            _recommendation_section(rec),
        ]
    )
    return {"report": markdown}
