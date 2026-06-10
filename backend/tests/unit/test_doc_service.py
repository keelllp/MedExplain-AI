"""Unit tests for native document extraction + magic-byte sniffing (no OCR)."""

import pymupdf
import pytest
from PIL import Image

from app.services import doc_service

pytestmark = pytest.mark.unit


def _make_text_pdf(path, text="Hemoglobin 13.5 g/dL"):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def test_sniff_mime_recognizes_supported_types():
    assert doc_service.sniff_mime(b"%PDF-1.7\n...") == "application/pdf"
    assert doc_service.sniff_mime(b"\xff\xd8\xff\xe0JFIF") == "image/jpeg"
    assert doc_service.sniff_mime(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert doc_service.sniff_mime(b"plain text, not a known type") is None


def test_native_pdf_extraction(tmp_path):
    pdf = tmp_path / "report.pdf"
    _make_text_pdf(pdf, "Hemoglobin 13.5 g/dL")
    extraction = doc_service.load(str(pdf), "application/pdf")

    assert extraction.page_count == 1
    assert len(extraction.pages) == 1
    assert "Hemoglobin" in extraction.pages[0].text
    assert extraction.pages[0].needs_ocr is False  # has a real text layer


def test_image_page_always_needs_ocr(tmp_path):
    png = tmp_path / "scan.png"
    Image.new("RGB", (32, 32), "white").save(str(png))
    extraction = doc_service.load(str(png), "image/png")

    assert extraction.page_count == 1
    assert extraction.pages[0].needs_ocr is True
    assert extraction.pages[0].text == ""
