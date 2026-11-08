"""Unit tests for structured invoice field extraction, schema validation, and edge cases."""

from decimal import Decimal
from pathlib import Path

import pytest

from documind.extraction.field_extractor import StructuredInvoiceExtractor
from documind.extraction.service import ExtractionService
from documind.schemas.invoice import EvidenceStatus


@pytest.fixture(scope="module")
def extractor() -> StructuredInvoiceExtractor:
    return StructuredInvoiceExtractor()


@pytest.fixture(scope="module")
def extraction_service() -> ExtractionService:
    return ExtractionService()


@pytest.mark.unit
def test_extract_digital_standard(
    extractor: StructuredInvoiceExtractor,
    extraction_service: ExtractionService,
) -> None:
    """Verify standard digital invoice extraction and full schema validation."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_001_digital.pdf").read_bytes()
    raw_res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-001")
    record = extractor.extract(raw_res, file_name="syn_invoice_001_digital.pdf")

    assert record.validation_passed
    assert record.review_status == "approved"
    assert record.data is not None

    assert record.data.invoice_number == "INV-2024-0001"
    assert record.data.vendor_name == "Beacon Logistics GmbH"
    assert record.data.currency == "EUR"
    assert record.data.subtotal == Decimal("535.50")
    assert record.data.tax == Decimal("53.55")
    assert record.data.total == Decimal("589.05")
    assert len(record.data.line_items) == 2

    # Verify evidence
    assert "invoice_number" in record.evidence
    ev_inv = record.evidence["invoice_number"]
    assert ev_inv.status == EvidenceStatus.EXTRACTED
    assert ev_inv.bounding_box is not None
    assert ev_inv.source_method == "native_text"


@pytest.mark.unit
def test_missing_invoice_number_handling(
    extractor: StructuredInvoiceExtractor,
    extraction_service: ExtractionService,
) -> None:
    """Verify that omitted invoice numbers produce honest missing evidence and fail schema validation."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_007_digital.pdf").read_bytes()
    raw_res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-007")
    record = extractor.extract(raw_res, file_name="syn_invoice_007_digital.pdf")

    assert not record.validation_passed
    assert record.review_status == "needs_review"
    assert record.data is None  # Fails schema validation due to missing required field
    assert any("invoice_number" in err for err in record.validation_errors)

    ev_inv = record.evidence["invoice_number"]
    assert ev_inv.status == EvidenceStatus.MISSING
    assert ev_inv.extracted_value is None


@pytest.mark.unit
def test_missing_vendor_handling(
    extractor: StructuredInvoiceExtractor,
    extraction_service: ExtractionService,
) -> None:
    """Verify that omitted vendor names produce missing evidence and trigger review."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_018_digital.pdf").read_bytes()
    raw_res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-018")
    record = extractor.extract(raw_res, file_name="syn_invoice_018_digital.pdf")

    assert not record.validation_passed
    assert record.review_status == "needs_review"
    ev_vend = record.evidence["vendor_name"]
    assert ev_vend.status == EvidenceStatus.MISSING
    assert ev_vend.extracted_value is None


@pytest.mark.unit
def test_ambiguous_date_handling(
    extractor: StructuredInvoiceExtractor,
    extraction_service: ExtractionService,
) -> None:
    """Verify that ambiguous date formats flag ambiguity in evidence without guessing."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_023_digital.pdf").read_bytes()
    raw_res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-023")
    record = extractor.extract(raw_res, file_name="syn_invoice_023_digital.pdf")

    ev_date = record.evidence["invoice_date"]
    assert ev_date.status == EvidenceStatus.AMBIGUOUS
    assert len(ev_date.candidates) == 2
    assert "2024-03-04" in ev_date.candidates
    assert "2024-04-03" in ev_date.candidates


@pytest.mark.unit
def test_european_number_parsing(
    extractor: StructuredInvoiceExtractor,
    extraction_service: ExtractionService,
) -> None:
    """Verify that European format dot-thousands and comma-decimal parse cleanly to Decimal."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_027_digital.pdf").read_bytes()
    raw_res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-027")
    record = extractor.extract(raw_res, file_name="syn_invoice_027_digital.pdf")

    assert record.validation_passed
    assert record.data is not None
    assert record.data.total == Decimal("649.00")
    assert record.data.subtotal == Decimal("590.00")
    assert record.data.tax == Decimal("59.00")


@pytest.mark.unit
def test_scanned_ocr_extraction(
    extractor: StructuredInvoiceExtractor,
    extraction_service: ExtractionService,
) -> None:
    """Verify that OCR extracted values contain valid coordinates and OCR confidence scores."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_031_scanned.pdf").read_bytes()
    raw_res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-031")
    record = extractor.extract(raw_res, file_name="syn_invoice_031_scanned.pdf")

    assert record.validation_passed
    assert record.data is not None
    assert record.data.invoice_number == "INV-2024-0031"
    assert record.data.total == Decimal("589.05")

    ev_inv = record.evidence["invoice_number"]
    assert ev_inv.source_method == "ocr"
    assert ev_inv.ocr_confidence is not None
    assert 0.0 <= ev_inv.ocr_confidence <= 1.0


@pytest.mark.unit
def test_deterministic_extraction(
    extractor: StructuredInvoiceExtractor,
    extraction_service: ExtractionService,
) -> None:
    """Verify repeated extractions of the same document produce identical outputs."""
    pdf_bytes = Path("data/synthetic_documents/syn_invoice_001_digital.pdf").read_bytes()
    raw_res = extraction_service.extract_from_bytes(pdf_bytes, document_id="DOC-SYN-001")

    rec1 = extractor.extract(raw_res, file_name="syn_invoice_001_digital.pdf")
    rec2 = extractor.extract(raw_res, file_name="syn_invoice_001_digital.pdf")

    assert rec1.data == rec2.data
    assert rec1.validation_passed == rec2.validation_passed
    assert len(rec1.evidence) == len(rec2.evidence)
