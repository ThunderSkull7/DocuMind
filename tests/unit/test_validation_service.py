"""Unit tests for ValidationService aggregation and status transitions."""

from datetime import date
from decimal import Decimal

import pytest

from documind.schemas.invoice import (
    EvidenceStatus,
    ExtractionMethod,
    FieldEvidence,
    InvoiceExtractionRecord,
)
from documind.validation.models import OverallValidationStatus
from documind.validation.service import ValidationService


@pytest.fixture
def service() -> ValidationService:
    return ValidationService()


@pytest.mark.unit
def test_validation_clean_invoice(service: ValidationService) -> None:
    """Verify completely consistent invoice returns VALID status."""
    record = InvoiceExtractionRecord(
        document_id="VAL-001",
        file_name="clean.pdf",
        raw_fields={
            "invoice_number": "INV-2024-0001",
            "invoice_date": date(2024, 5, 1),
            "due_date": date(2024, 5, 31),
            "vendor_name": "Beacon Logistics GmbH",
            "currency": "EUR",
            "subtotal": Decimal("100.00"),
            "tax": Decimal("10.00"),
            "total": Decimal("110.00"),
            "line_items": [],
        },
    )

    res = service.validate_record(record)
    assert res.overall_status == OverallValidationStatus.VALID
    assert res.rules_failed == 0
    assert len(res.discrepancies) == 0
    assert "Approve" in res.recommended_action


@pytest.mark.unit
def test_validation_critical_missing_field(service: ValidationService) -> None:
    """Verify missing mandatory invoice number yields INVALID status."""
    record = InvoiceExtractionRecord(
        document_id="VAL-002",
        file_name="missing_inv.pdf",
        raw_fields={
            "invoice_number": None,
            "invoice_date": date(2024, 5, 1),
            "vendor_name": "Beacon Logistics GmbH",
            "currency": "EUR",
            "total": Decimal("110.00"),
        },
        evidence={
            "invoice_number": FieldEvidence(
                field_name="invoice_number",
                raw_text="[NOT SPECIFIED]",
                confidence=0.0,
                method=ExtractionMethod.RULE_BASED,
                status=EvidenceStatus.MISSING,
            )
        },
    )

    res = service.validate_record(record)
    assert res.overall_status == OverallValidationStatus.INVALID
    assert res.rules_failed >= 1
    assert "Reject" in res.recommended_action


@pytest.mark.unit
def test_validation_arithmetic_mismatch_needs_review(service: ValidationService) -> None:
    """Verify arithmetic mismatch yields NEEDS_REVIEW status."""
    record = InvoiceExtractionRecord(
        document_id="VAL-003",
        file_name="bad_math.pdf",
        raw_fields={
            "invoice_number": "INV-2024-0003",
            "invoice_date": date(2024, 5, 1),
            "vendor_name": "Beacon Logistics GmbH",
            "currency": "EUR",
            "subtotal": Decimal("100.00"),
            "tax": Decimal("10.00"),
            "total": Decimal("150.00"),  # Expected: 110.00
        },
    )

    res = service.validate_record(record)
    assert res.overall_status == OverallValidationStatus.NEEDS_REVIEW
    assert res.rules_failed >= 1
    assert "Route to human accounts payable review" in res.recommended_action


@pytest.mark.unit
def test_validation_ambiguous_date_warning(service: ValidationService) -> None:
    """Verify ambiguous date yields VALID_WITH_WARNINGS status."""
    record = InvoiceExtractionRecord(
        document_id="VAL-004",
        file_name="ambiguous.pdf",
        raw_fields={
            "invoice_number": "INV-2024-0004",
            "invoice_date": date(2024, 4, 3),
            "due_date": date(2024, 5, 1),
            "vendor_name": "Beacon Logistics GmbH",
            "currency": "EUR",
            "subtotal": Decimal("100.00"),
            "tax": Decimal("10.00"),
            "total": Decimal("110.00"),
        },
        evidence={
            "invoice_date": FieldEvidence(
                field_name="invoice_date",
                raw_text="03/04/2024",
                confidence=0.5,
                method=ExtractionMethod.PATTERN,
                status=EvidenceStatus.AMBIGUOUS,
                candidates=["2024-03-04", "2024-04-03"],
            )
        },
    )

    res = service.validate_record(record)
    assert res.overall_status == OverallValidationStatus.VALID_WITH_WARNINGS
    assert res.rules_warning >= 1
    assert res.rules_failed == 0
