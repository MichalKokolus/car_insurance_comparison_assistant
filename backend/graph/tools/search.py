"""web_search tool bound to the market-research ReAct agent.

Backed by DuckDuckGo (via `ddgs`) — no API key required. Returns raw search results (title,
snippet, url); the agent reads them and a downstream structured-extraction step turns them into
`Offer` objects. Returns a JSON error object on failure so the agent can carry on.

Note: Slovak PZP/kasko *premiums* live behind per-insurer quote forms, so search snippets rarely
contain concrete prices — expect sparse extraction and a labelled sample fallback (see
`market_research`). Swap this tool for a quote-form integration to get real premiums.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web for current Slovak car-insurance (PZP/kasko) offers and prices.

    Returns a JSON array of {title, snippet, url} results.
    """
    try:
        from ddgs import DDGS

        results = DDGS().text(query, region="sk-sk", max_results=8)
        cleaned = [
            {"title": r.get("title"), "snippet": r.get("body"), "url": r.get("href")}
            for r in results
        ]
        return json.dumps(cleaned, ensure_ascii=False)
    except Exception as exc:  # rate limits / network — let the agent proceed
        return json.dumps({"error": str(exc), "results": []}, ensure_ascii=False)
