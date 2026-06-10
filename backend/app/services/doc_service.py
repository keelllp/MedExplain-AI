"""Document loading + native-text/table extraction (PyMuPDF + pdfplumber).

Native-text-first: for digital PDFs we read the embedded text layer and tables
directly (fast, exact, no OCR). Only pages with no usable text layer — and image
uploads (JPG/PNG) — are flagged for OCR (handled by ocr_service). This is the
single biggest CPU win on a laptop: we never OCR a text-native PDF.

DoS guards: page-count cap, and a pixel cap on both PDF page rendering and image
decoding (defends against pixel bombs / decompression bombs on a single CPU worker).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pdfplumber
import pymupdf
from PIL import Image

from app.core.config import settings

# Hard backstop for PIL on top of the explicit size checks below.
Image.MAX_IMAGE_PIXELS = settings.max_image_pixels

# ---- upload validation helpers -------------------------------------------------

ALLOWED_MIMES = ("application/pdf", "image/jpeg", "image/png")
EXT_BY_MIME = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}

# A page with fewer than this many non-whitespace chars has no usable text layer
# (essentially blank / scanned image) and is routed to OCR.
_MIN_NATIVE_CHARS = 10


class ExtractionError(RuntimeError):
    """Document cannot be processed safely (too many pages / oversized page or image)."""


def sniff_mime(head: bytes) -> str | None:
    """Detect the file type from magic bytes (do not trust the client content-type)."""
    if head[:5] == b"%PDF-":
        return "application/pdf"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return None


# ---- extraction ----------------------------------------------------------------


@dataclass
class PageContent:
    index: int
    text: str
    needs_ocr: bool


@dataclass
class DocExtraction:
    page_count: int
    pages: list[PageContent] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)  # {"page": int, "rows": [[cell, ...], ...]}


def load(stored_path: str, mime_type: str) -> DocExtraction:
    """Extract native text + tables; flag pages that still need OCR."""
    if mime_type == "application/pdf":
        return _load_pdf(stored_path)
    if mime_type in ("image/jpeg", "image/png"):
        return DocExtraction(page_count=1, pages=[PageContent(0, "", needs_ocr=True)])
    raise ValueError(f"Unsupported mime_type for extraction: {mime_type}")


def _load_pdf(path: str) -> DocExtraction:
    pages: list[PageContent] = []
    with pymupdf.open(path) as doc:
        page_count = doc.page_count
        if page_count > settings.max_pages:
            raise ExtractionError(f"PDF has {page_count} pages (limit {settings.max_pages})")
        for i in range(page_count):
            text = doc[i].get_text("text").strip()
            needs_ocr = len(text.replace(" ", "").replace("\n", "")) < _MIN_NATIVE_CHARS
            pages.append(PageContent(index=i, text=text, needs_ocr=needs_ocr))

    tables: list[dict] = []
    # pdfplumber is better at digital-PDF tables than PyMuPDF; ignore failures per page.
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                for tbl in page.extract_tables() or []:
                    tables.append({"page": i, "rows": tbl})
    except Exception:  # noqa: BLE001 - table extraction is best-effort
        pass

    return DocExtraction(page_count=page_count, pages=pages, tables=tables)


def _clamp_dpi(width_pt: float, height_pt: float, requested_dpi: int) -> int:
    """Lower the render DPI so total pixels stay under the configured cap."""
    w_in = max(width_pt / 72.0, 0.01)
    h_in = max(height_pt / 72.0, 0.01)
    max_dpi = (settings.max_image_pixels / (w_in * h_in)) ** 0.5
    return max(72, min(requested_dpi, int(max_dpi)))


def page_image_png(stored_path: str, mime_type: str, index: int, dpi: int = 200) -> bytes:
    """Return PNG bytes for the given page (for OCR). Renders PDF pages; re-encodes images."""
    if mime_type == "application/pdf":
        with pymupdf.open(stored_path) as doc:
            page = doc[index]
            safe_dpi = _clamp_dpi(page.rect.width, page.rect.height, dpi)
            return page.get_pixmap(dpi=safe_dpi).tobytes("png")

    # image upload: bound pixels before decoding into memory, then normalize to PNG
    with Image.open(stored_path) as img:
        if img.width * img.height > settings.max_image_pixels:
            raise ExtractionError(f"image too large: {img.width}x{img.height} px")
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
