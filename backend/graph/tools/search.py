"""web_search tool bound to the market-research ReAct agent.

PoC stub: returns the canned offers regardless of query. This is the single seam to replace with a
real search API (Tavily/Serper/DuckDuckGo) to make research live — no other node changes.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from backend.data.offers import CANNED_OFFERS


@tool
def web_search(query: str) -> str:
    """Search for current Slovak car-insurance (PZP/kasko) offers. Returns a JSON list of offers."""
    return json.dumps(
        [offer.model_dump() for offer in CANNED_OFFERS],
        ensure_ascii=False,
        default=str,
    )
