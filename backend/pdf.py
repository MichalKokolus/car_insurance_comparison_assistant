"""PDF text extraction. Kept deliberately simple: text layer only, no OCR/vision."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_text(data: bytes) -> str:
    """Extract concatenated text from a PDF's pages. Returns "" on any failure."""
    try:
        reader = PdfReader(BytesIO(data))
        parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(parts).strip()
    except Exception:
        return ""
