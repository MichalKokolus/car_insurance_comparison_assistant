"""verify_offers — stub-mode passthrough and the pure evidence-matching helpers."""

import json

from backend.data.offers import CANNED_OFFERS
from backend.graph.nodes.verify_offers import _collect_raw_results, _make_evidence_tool, verify_offers


async def test_stub_mode_passes_offers_through_unchanged():
    state = {"market_offers": list(CANNED_OFFERS), "research_log": []}
    result = await verify_offers(state)
    assert result["market_offers"] == list(CANNED_OFFERS)


def test_collect_raw_results_flattens_sources_with_snippets():
    log = [
        {"query": "q1", "sources": [{"title": "a", "url": "u1", "snippet": "168 EUR Union"}]},
        {"query": "q2", "sources": [{"title": "b", "url": "u2", "snippet": None}]},
    ]
    flat = _collect_raw_results(log)
    assert len(flat) == 1
    assert flat[0]["url"] == "u1"


def test_evidence_tool_confirms_price_despite_diacritics_mismatch():
    # The snippet's plain-ASCII "poistovna" should still match the accented "poisťovňa" argument —
    # this is the exact false negative the naive substring matcher used to produce.
    raw = [{"title": "Union PZP", "snippet": "Union poistovna PZP za 168 eur rocne", "url": "u1"}]
    tool = _make_evidence_tool(raw)
    out = json.loads(tool.invoke({"insurer": "Union poisťovňa", "premium": 168.0}))
    assert out["status"] == "price_confirmed"
    assert out["sources"][0]["url"] == "u1"


def test_evidence_tool_confirms_price_with_comma_decimal_and_currency_symbol():
    raw = [{"title": "Union", "snippet": "Union PZP od 168,00 € rocne", "url": "u1"}]
    tool = _make_evidence_tool(raw)
    out = json.loads(tool.invoke({"insurer": "Union", "premium": 168.0}))
    assert out["status"] == "price_confirmed"


def test_evidence_tool_reports_insurer_mentioned_but_price_unconfirmed():
    raw = [{"title": "Union", "snippet": "Union poistovna ponuka PZP poistenie", "url": "u1"}]
    tool = _make_evidence_tool(raw)
    out = json.loads(tool.invoke({"insurer": "Union", "premium": 168.0}))
    assert out["status"] == "mentioned_unconfirmed"


def test_evidence_tool_reports_no_evidence():
    tool = _make_evidence_tool([])
    out = json.loads(tool.invoke({"insurer": "Nobody", "premium": 999.0}))
    assert out["status"] == "no_evidence"
