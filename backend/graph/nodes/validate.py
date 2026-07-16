"""validate — pure Python. Checks required fields; pauses for human input if any are missing."""

from __future__ import annotations

from datetime import date

from langgraph.types import interrupt

from backend.graph.state import AppState
from backend.schemas import PolicyData

REQUIRED_FIELDS = ["anniversary_date", "notice_period_days"]

QUESTIONS = {
    "anniversary_date": "What is your policy's anniversary / renewal date? (YYYY-MM-DD)",
    "notice_period_days": "How many days before renewal must the cancellation be delivered? (e.g. 42)",
}


def _missing(policy: PolicyData) -> list[str]:
    return [f for f in REQUIRED_FIELDS if getattr(policy, f, None) in (None, "")]


def _apply(policy: PolicyData, answers: dict) -> None:
    for key, value in (answers or {}).items():
        if value in (None, ""):
            continue
        if key == "anniversary_date" and not isinstance(value, date):
            try:
                value = date.fromisoformat(str(value))
            except ValueError:
                continue
        if key == "notice_period_days":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        if hasattr(policy, key):
            setattr(policy, key, value)


async def validate(state: AppState) -> dict:
    policy = state["policy"]
    answers = dict(state.get("user_answers") or {})
    _apply(policy, answers)

    missing = _missing(policy)
    if missing:
        # Suspend the graph. The value passed to interrupt() is surfaced to the client; the value
        # returned here is whatever the client sends back via Command(resume=...).
        provided = interrupt(
            {"missing_fields": missing, "questions": {f: QUESTIONS[f] for f in missing}}
        )
        provided = provided or {}
        answers.update(provided)
        _apply(policy, provided)
        missing = _missing(policy)

    return {"policy": policy, "user_answers": answers, "missing_fields": missing}
