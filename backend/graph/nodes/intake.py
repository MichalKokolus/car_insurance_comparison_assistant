"""intake — PDF → structured PolicyData.

Primary path: feed the extracted text to the model. If text extraction came back near-empty (a
scanned/image PDF) and a real model is configured, fall back to sending the rendered page images
so the model can read the scan.
"""

from __future__ import annotations

import base64

from backend.graph.state import AppState
from backend.pdf import render_pdf_to_images
from backend.schemas import PolicyData
from backend.services.llm.anthropic_provider import AnthropicProvider
from backend.services.llm.factory import get_provider

# Below this many characters of extracted text, assume extraction failed (likely a scanned PDF).
_MIN_TEXT_CHARS = 40

_SYSTEM = (
    "You extract structured car-insurance policy data from a Slovak policy document. "
    "Fill only fields you are confident about. If a value is not present in the document, set that "
    "field to null — never invent a value and never use placeholder strings like '<UNKNOWN>', "
    "'N/A', or '-'. coverage_type is 'PZP' (mandatory liability) or 'kasko' (comprehensive)."
)


async def intake(state: AppState) -> dict:
    provider = get_provider()
    text = (state.get("pdf_text") or "").strip()

    # Text path — enough extracted text, or the stub (which ignores the input anyway).
    if len(text) >= _MIN_TEXT_CHARS or not isinstance(provider, AnthropicProvider):
        source = text or "(no text could be extracted from the PDF)"
        policy = await provider.structured(
            _SYSTEM, f"Policy document text:\n\n{source[:6000]}", PolicyData
        )
        return {"policy": policy}

    # Vision fallback — near-empty text + a real model: try reading the pages as images.
    pdf_b64 = state.get("pdf_b64") or ""
    images = render_pdf_to_images(base64.b64decode(pdf_b64)) if pdf_b64 else []
    if not images:
        policy = await provider.structured(_SYSTEM, "(no readable text in the PDF)", PolicyData)
        return {"policy": policy}

    policy = await provider.structured_with_images(
        _SYSTEM,
        "These are scanned images of a car-insurance policy's pages. Extract the policy fields.",
        images,
        PolicyData,
    )
    return {"policy": policy}
