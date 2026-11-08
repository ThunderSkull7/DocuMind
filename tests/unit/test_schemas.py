"""Unit tests for DocuMind invoice schemas and evidence models."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from documind.schemas import (
    BoundingBox,
    ExtractionMethod,
    FieldEvidence,
    InvoiceData,
    InvoiceExtractionRecord,
)


@pytest.mark.unit
def test_valid_invoice_data() -> None:
    """Verify that a valid invoice dictionary parses cleanly."""
    invoice = InvoiceData(
        invoice_number="INV-2024-001",
        invoice_date=date(2024, 10, 15),
        vendor_name="Acme Corp",
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        total=Decimal("110.00"),
    )
    assert invoice.invoice_number == "INV-2024-001"
    assert invoice.total == Decimal("110.00")
    assert invoice.tax == Decimal("10.00")


@pytest.mark.unit
def test_invoice_missing_required_field() -> None:
    """Verify that omitting a required field (e.g., total) raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        InvoiceData(
            invoice_number="INV-2024-002",
            invoice_date=date(2024, 10, 15),
            vendor_name="Acme Corp",
            currency="USD",
            # total omitted
        )
    assert "total" in str(exc_info.value)


@pytest.mark.unit
def test_invoice_extra_fields_forbidden() -> None:
    """Verify that extra unknown fields are rejected."""
    with pytest.raises(ValidationError):
        InvoiceData(
            invoice_number="INV-2024-003",
            invoice_date=date(2024, 10, 15),
            vendor_name="Acme Corp",
            currency="USD",
            total=Decimal("100.00"),
            unexpected_field="disallowed",
        )


@pytest.mark.unit
def test_field_evidence_model() -> None:
    """Verify FieldEvidence and BoundingBox instantiation and validation."""
    bbox = BoundingBox(page=1, x0=10.0, y0=20.0, x1=150.0, y1=45.0)
    evidence = FieldEvidence(
        raw_text="INV-2024-001",
        confidence=0.98,
        method=ExtractionMethod.NATIVE_TEXT,
        bounding_box=bbox,
        page_number=1,
    )
    assert evidence.confidence == 0.98
    assert evidence.method == ExtractionMethod.NATIVE_TEXT
    assert evidence.bounding_box.page == 1


@pytest.mark.unit
def test_extraction_record() -> None:
    """Verify InvoiceExtractionRecord container initialization."""
    record = InvoiceExtractionRecord(
        document_id="doc-12345",
        file_name="sample_invoice.pdf",
    )
    assert record.document_id == "doc-12345"
    assert record.review_status == "pending"
    assert not record.validation_passed
