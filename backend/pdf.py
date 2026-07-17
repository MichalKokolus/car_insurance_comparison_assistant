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


def render_pdf_to_images(data: bytes, max_pages: int = 5, dpi: int = 150) -> list[bytes]:
    """Rasterize the first pages of a PDF to PNG bytes (for the vision fallback on scanned PDFs).

    Returns [] on any failure (missing lib, unreadable PDF).
    """
    try:
        import pymupdf
    except Exception:
        return []

    images: list[bytes] = []
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        for i in range(min(max_pages, doc.page_count)):
            pix = doc[i].get_pixmap(dpi=dpi)
            images.append(pix.tobytes("png"))
        doc.close()
    except Exception:
        return []
    return images
