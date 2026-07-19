"""verify_offers — the second agent: a fact-checking ReAct agent over the raw search evidence.

Stub mode, no candidate offers, or no live search evidence to check against: no-op passthrough.
Real provider: a second, independent `create_react_agent` (separate from market_research's search
agent) whose one tool lets it check whether a claimed insurer+premium is actually backed by a
snippet the first agent collected. The tool reports one of three graded outcomes rather than a
plain yes/no — Slovak insurer premiums routinely sit behind per-insurer quote forms (see
`graph/tools/search.py`), so "the insurer is mentioned but no snippet states this price" is a
common, honest outcome, not the same as finding no trace of the insurer at all. The match itself is
diacritics/case-insensitive and tolerates the currency/decimal formatting variance ("168", "168,00",
"168.00 €", ...) that a naive substring check misses. Offers already labelled as sample data
(`data/offers.py:SAMPLE_SOURCE_LABEL`) are skipped — they're already honestly marked as synthetic.
"""

from __future__ import annotations

import json
import re
import unicodedata

from backend.data.offers import SAMPLE_SOURCE_LABEL
from backend.graph.state import AppState
from backend.schemas import OfferVerificationList
from backend.services.llm.factory import get_provider
from backend.services.llm.stub_provider import StubProvider

# Second in-code cost guardrail, scoped to this agent's own tool-call loop — mirrors
# RESEARCH_RECURSION_LIMIT in market_research.py.
VERIFY_RECURSION_LIMIT = 8

_VERIFY_EXTRACT_SYSTEM = (
    "From the fact-checking agent's notes below, extract one verdict per offer it discussed: "
    "insurer, annual_premium, status (one of 'price_confirmed', 'mentioned_unconfirmed', "
    "'no_evidence' — taken directly from what check_evidence reported for that offer), and a "
    "one-sentence reason."
)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _normalize(text: str) -> str:
    """Lowercase and strip diacritics so 'Union poisťovňa' matches 'union poistovna' text."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _numbers_in(text: str) -> list[float]:
    """Extract numbers from text, treating both ',' and '.' as decimal separators."""
    values = []
    for match in _NUMBER_RE.finditer(text):
        try:
            values.append(float(match.group().replace(",", ".")))
        except ValueError:
            continue
    return values


def _premium_mentioned(text: str, premium: float) -> bool:
    return any(abs(value - premium) < 1.0 for value in _numbers_in(text))


def _collect_raw_results(research_log: list[dict]) -> list[dict]:
    """Flatten every source (with its snippet) the research agent collected across all queries."""
    return [
        source
        for entry in research_log
        for source in entry.get("sources", [])
        if source.get("snippet")
    ]


def _make_evidence_tool(raw_results: list[dict]):
    from langchain_core.tools import tool

    @tool
    def check_evidence(insurer: str, premium: float) -> str:
        """Check whether collected search snippets mention this insurer, and whether any of those
        also state this premium. Returns one of three statuses: 'price_confirmed' (a snippet
        mentions both), 'mentioned_unconfirmed' (the insurer is mentioned but no snippet states
        this price), or 'no_evidence' (the insurer isn't mentioned in any collected snippet)."""
        insurer_norm = _normalize(insurer)
        price_matches, insurer_only_matches = [], []
        for r in raw_results:
            text = _normalize(f"{r.get('title', '')} {r.get('snippet', '')}")
            if insurer_norm not in text:
                continue
            (price_matches if _premium_mentioned(text, premium) else insurer_only_matches).append(r)

        if price_matches:
            payload = {"status": "price_confirmed", "sources": price_matches[:2]}
        elif insurer_only_matches:
            payload = {"status": "mentioned_unconfirmed", "sources": insurer_only_matches[:2]}
        else:
            payload = {"status": "no_evidence"}
        return json.dumps(payload, ensure_ascii=False)

    return check_evidence


_SOURCE_NOTE = {
    "price_confirmed": "verified",
    "mentioned_unconfirmed": "insurer found, price unconfirmed",
    "no_evidence": "unverified",
}


async def verify_offers(state: AppState) -> dict:
    provider = get_provider()
    offers = list(state.get("market_offers") or [])
    candidates = [o for o in offers if o.source != SAMPLE_SOURCE_LABEL]
    raw_results = _collect_raw_results(state.get("research_log") or [])

    if isinstance(provider, StubProvider) or not candidates or not raw_results:
        return {"market_offers": offers}

    from langgraph.prebuilt import create_react_agent

    evidence_tool = _make_evidence_tool(raw_results)
    offers_desc = "\n".join(
        f"- {o.insurer} / {o.product}: EUR {o.annual_premium}/year" for o in candidates
    )
    prompt = (
        "You are a fact-checking agent, independent from the agent that found these offers. For "
        "each candidate offer below, call check_evidence with its insurer and premium and report "
        "back the status it returns. Report a verdict for every offer.\n\n"
        f"Candidate offers:\n{offers_desc}"
    )
    try:
        agent = create_react_agent(provider.chat_model(), tools=[evidence_tool])
        result = await agent.ainvoke(
            {"messages": [("user", prompt)]},
            config={"recursion_limit": VERIFY_RECURSION_LIMIT},
        )
        notes = result["messages"][-1].content
        if isinstance(notes, list):
            notes = " ".join(b.get("text", "") for b in notes if isinstance(b, dict))
        verdicts: OfferVerificationList = await provider.structured(
            _VERIFY_EXTRACT_SYSTEM, str(notes)[:4000], OfferVerificationList
        )
    except Exception:
        return {"market_offers": offers}  # verification is best-effort; never block the pipeline

    by_key = {
        (v.insurer.strip().lower(), round(v.annual_premium, 2)): v for v in verdicts.verifications
    }
    for offer in candidates:
        verdict = by_key.get((offer.insurer.strip().lower(), round(offer.annual_premium, 2)))
        if verdict is None:
            continue
        offer.source = f"{_SOURCE_NOTE[verdict.status]} — {verdict.reason}"

    return {"market_offers": offers}
