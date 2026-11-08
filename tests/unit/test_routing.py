"""Unit tests for hybrid page-level extraction routing."""

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest

from documind.config import Settings
from documind.extraction.models import (
    PageExtraction,
    PageExtractionMethod,
)
from documind.extraction.ocr import OCREngine
from documind.extraction.routing import PageExtractionRouter


@pytest.fixture
def mock_ocr_engine() -> OCREngine:
    """Provide an OCREngine mock that returns simulated OCR output."""
    engine = MagicMock(spec=OCREngine)

    def fake_extract_page(page: pymupdf.Page, page_number: int) -> PageExtraction:
        return PageExtraction(
            page_number=page_number,
            extraction_method=PageExtractionMethod.OCR,
            raw_text="RECOGNIZED OCR INVOICE TEXT FROM SCAN",
            normalized_text="RECOGNIZED OCR INVOICE TEXT FROM SCAN",
            text_blocks=[],
            word_count=6,
            character_count=37,
            page_width=float(page.rect.width),
            page_height=float(page.rect.height),
            quality=None,
            warnings=[],
        )

    engine.extract_page_ocr.side_effect = fake_extract_page
    return engine


@pytest.mark.unit
def test_digital_page_routes_to_native(temp_dir: Path, mock_ocr_engine: OCREngine) -> None:
    """Verify that a digital page with sufficient text routes to native extraction without calling OCR."""
    settings = Settings(project_root=temp_dir, ocr_enabled=True)
    router = PageExtractionRouter(settings=settings, ocr_engine=mock_ocr_engine)

    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    doc = pymupdf.open(str(pdf_path))
    page = doc[0]

    extracted_page, decision = router.route_and_extract_page(page, page_number=1)
    doc.close()

    assert decision.selected_method == PageExtractionMethod.NATIVE_TEXT
    assert not decision.fallback_triggered
    assert not decision.ocr_attempted
    assert extracted_page.extraction_method == PageExtractionMethod.NATIVE_TEXT
    assert mock_ocr_engine.extract_page_ocr.call_count == 0


@pytest.mark.unit
def test_scanned_page_routes_to_ocr(
    temp_dir: Path, mock_ocr_engine: OCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that an image-only scanned page triggers OCR fallback."""
    # Mock tesseract availability to True
    monkeypatch.setattr("documind.extraction.routing.is_tesseract_available", lambda *_: True)

    settings = Settings(project_root=temp_dir, ocr_enabled=True)
    router = PageExtractionRouter(settings=settings, ocr_engine=mock_ocr_engine)

    pdf_path = Path("data/synthetic_documents/syn_invoice_031_scanned.pdf")
    doc = pymupdf.open(str(pdf_path))
    page = doc[0]

    extracted_page, decision = router.route_and_extract_page(page, page_number=1)
    doc.close()

    assert decision.selected_method == PageExtractionMethod.OCR
    assert decision.fallback_triggered
    assert decision.ocr_attempted
    assert extracted_page.extraction_method == PageExtractionMethod.OCR
    assert mock_ocr_engine.extract_page_ocr.call_count == 1


@pytest.mark.unit
def test_mixed_document_routes_pages_independently(
    temp_dir: Path, mock_ocr_engine: OCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify routing evaluates each page independently in a mixed document."""
    monkeypatch.setattr("documind.extraction.routing.is_tesseract_available", lambda *_: True)

    settings = Settings(project_root=temp_dir, ocr_enabled=True)
    router = PageExtractionRouter(settings=settings, ocr_engine=mock_ocr_engine)

    # Build a synthetic mixed PDF: Page 1 has digital text, Page 2 is blank/image
    doc = pymupdf.open()
    p1 = doc.new_page(width=595.0, height=842.0)
    p1.insert_text(
        (50, 50),
        "This is genuine digital text for invoice processing with plenty of characters and words to meet native sufficiency thresholds easily.",
    )
    doc.new_page(width=595.0, height=842.0)
    # Page 2 has no text (simulating image or blank)

    res1, dec1 = router.route_and_extract_page(doc[0], page_number=1)
    res2, dec2 = router.route_and_extract_page(doc[1], page_number=2)
    doc.close()

    assert dec1.selected_method == PageExtractionMethod.NATIVE_TEXT
    assert dec2.selected_method == PageExtractionMethod.OCR
    assert res1.extraction_method == PageExtractionMethod.NATIVE_TEXT
    assert res2.extraction_method == PageExtractionMethod.OCR


@pytest.mark.unit
def test_ocr_disabled_behavior(temp_dir: Path, mock_ocr_engine: OCREngine) -> None:
    """Verify that when OCR is disabled, insufficient pages stay native with warnings."""
    settings = Settings(project_root=temp_dir, ocr_enabled=False)
    router = PageExtractionRouter(settings=settings, ocr_engine=mock_ocr_engine)

    doc = pymupdf.open()
    page = doc.new_page(width=595.0, height=842.0)  # Blank page
    res, dec = router.route_and_extract_page(page, page_number=1)
    doc.close()

    assert dec.selected_method == PageExtractionMethod.NATIVE_TEXT
    assert not dec.ocr_attempted
    assert any("OCR is disabled" in w for w in res.warnings)
    assert mock_ocr_engine.extract_page_ocr.call_count == 0


@pytest.mark.unit
def test_ocr_unavailable_behavior(
    temp_dir: Path, mock_ocr_engine: OCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that when Tesseract binary is missing, page stays native with clear warning."""
    monkeypatch.setattr("documind.extraction.routing.is_tesseract_available", lambda *_: False)

    settings = Settings(project_root=temp_dir, ocr_enabled=True)
    router = PageExtractionRouter(settings=settings, ocr_engine=mock_ocr_engine)

    doc = pymupdf.open()
    page = doc.new_page(width=595.0, height=842.0)  # Blank page
    res, dec = router.route_and_extract_page(page, page_number=1)
    doc.close()

    assert dec.selected_method == PageExtractionMethod.NATIVE_TEXT
    assert any("Tesseract OCR executable was not found" in w for w in res.warnings)
