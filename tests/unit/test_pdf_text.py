"""Unit tests for native PDF text extraction engine."""

from pathlib import Path

import pymupdf
import pytest

from documind.exceptions import PDFExtractionError
from documind.extraction.models import PageExtractionMethod
from documind.extraction.pdf_text import extract_native_document, extract_native_page


@pytest.mark.unit
def test_digital_pdf_extraction() -> None:
    """Verify native extraction on a standard synthetic digital invoice."""
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    pages = extract_native_document(pdf_path)

    assert len(pages) == 1
    p1 = pages[0]
    assert p1.page_number == 1
    assert p1.extraction_method == PageExtractionMethod.NATIVE_TEXT
    assert len(p1.raw_text) > 200
    assert "INVOICE" in p1.raw_text
    assert p1.word_count > 30
    assert p1.page_width == 595.0
    assert p1.page_height == 842.0
    assert p1.quality is not None
    assert p1.quality.is_sufficient_for_native


@pytest.mark.unit
def test_multipage_pdf_extraction() -> None:
    """Verify native extraction preserves boundaries across multipage documents."""
    pdf_path = Path("data/synthetic_documents/syn_invoice_010_digital.pdf")
    pages = extract_native_document(pdf_path)

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert pages[0].page_height == 842.0
    assert pages[1].page_height == 842.0
    assert pages[0].word_count > 0
    assert pages[1].word_count > 0


@pytest.mark.unit
def test_bounding_box_validity() -> None:
    """Verify all word bounding boxes are well-formed and fit within page boundaries."""
    pdf_path = Path("data/synthetic_documents/syn_invoice_002_digital.pdf")
    pages = extract_native_document(pdf_path)
    p = pages[0]

    for block in p.text_blocks:
        assert 0.0 <= block.bounding_box.x0 <= block.bounding_box.x1 <= p.page_width
        assert 0.0 <= block.bounding_box.y0 <= block.bounding_box.y1 <= p.page_height

        for word in block.words:
            assert word.confidence is None  # Native text must explicitly have None confidence
            assert 0.0 <= word.bounding_box.x0 <= word.bounding_box.x1 <= p.page_width
            assert 0.0 <= word.bounding_box.y0 <= word.bounding_box.y1 <= p.page_height
            assert word.page_number == p.page_number


@pytest.mark.unit
def test_empty_page_handling() -> None:
    """Verify an empty PDF page extracts cleanly without crashing."""
    doc = pymupdf.open()
    page = doc.new_page(width=500.0, height=700.0)
    extracted = extract_native_page(page, page_number=1)
    doc.close()

    assert extracted.character_count == 0
    assert extracted.word_count == 0
    assert extracted.raw_text == ""
    assert extracted.normalized_text == ""
    assert len(extracted.text_blocks) == 0
    assert extracted.quality is not None
    assert not extracted.quality.is_sufficient_for_native


@pytest.mark.unit
def test_reading_order_preservation() -> None:
    """Verify word tokens preserve sequential reading order index."""
    pdf_path = Path("data/synthetic_documents/syn_invoice_003_digital.pdf")
    pages = extract_native_document(pdf_path)
    all_words = [w for b in pages[0].text_blocks for w in b.words]

    for expected_idx, word in enumerate(all_words):
        assert word.reading_order_index == expected_idx


@pytest.mark.unit
def test_invalid_pdf_handling() -> None:
    """Verify invalid PDF bytes raise PDFExtractionError."""
    with pytest.raises(PDFExtractionError):
        extract_native_document(b"Corrupted garbage non-pdf content")
