"""Unit tests for spatial line-item extraction."""

from decimal import Decimal
from pathlib import Path

import pytest

from documind.extraction.line_item_extractor import LineItemExtractor
from documind.extraction.service import ExtractionService


@pytest.fixture(scope="module")
def extraction_service() -> ExtractionService:
    return ExtractionService()


@pytest.fixture(scope="module")
def line_item_extractor() -> LineItemExtractor:
    return LineItemExtractor()


@pytest.mark.unit
def test_extract_line_items_digital(
    extraction_service: ExtractionService,
    line_item_extractor: LineItemExtractor,
) -> None:
    """Verify extracting line items from digital invoice tables."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_001_digital.pdf").read_bytes()
    res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-001")
    items = line_item_extractor.extract_line_items_from_pages(res.pages)

    assert len(items) == 2
    item1 = items[0]
    assert item1.description == "Database Managed Storage (TB/month)"
    assert item1.quantity == Decimal("1")
    assert item1.unit_price == Decimal("85.50")
    assert item1.total == Decimal("85.50")
    assert item1.bounding_box is not None
    assert item1.page_number == 1

    item2 = items[1]
    assert item2.description == "Security & Compliance Audit Service"
    assert item2.quantity == Decimal("1")
    assert item2.unit_price == Decimal("450.00")
    assert item2.total == Decimal("450.00")


@pytest.mark.unit
def test_extract_line_items_scanned(
    extraction_service: ExtractionService,
    line_item_extractor: LineItemExtractor,
) -> None:
    """Verify line item extraction from OCR scanned pages with deskewing."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_038_scanned.pdf").read_bytes()
    res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-038")
    items = line_item_extractor.extract_line_items_from_pages(res.pages)

    assert len(items) == 2
    assert "Logistics Freight Dispatch Fee" in items[0].description
    assert items[0].quantity == Decimal("2")
    assert items[0].unit_price == Decimal("180.00")
    assert items[0].total == Decimal("360.00")
