"""Unit tests for duplicate invoice screening across documents."""

from datetime import date
from decimal import Decimal

import pytest

from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.duplicate_detection import DuplicateDetector
from documind.validation.models import DuplicateMatchType, Severity, ValidationOutcome


@pytest.fixture
def prior_record() -> InvoiceExtractionRecord:
    return InvoiceExtractionRecord(
        document_id="DOC-PRIOR-001",
        file_name="prior_invoice.pdf",
        raw_fields={
            "invoice_number": "INV-2024-9999",
            "vendor_name": "Apex Cloud Systems Inc.",
            "invoice_date": date(2024, 6, 1),
            "total": Decimal("500.00"),
        },
    )


@pytest.mark.unit
def test_exact_identity_duplicate(prior_record: InvoiceExtractionRecord) -> None:
    """Verify same vendor and invoice number triggers EXACT_IDENTITY match."""
    detector = DuplicateDetector(historical_records=[prior_record])

    candidate = InvoiceExtractionRecord(
        document_id="DOC-CAND-002",
        file_name="candidate.pdf",
        raw_fields={
            "invoice_number": "INV-2024-9999",  # Identical
            "vendor_name": "Apex Cloud Systems Inc.",  # Identical
            "invoice_date": date(2024, 6, 1),
            "total": Decimal("500.00"),
        },
    )

    res, disc = detector.check_duplicate(candidate)
    assert res.is_duplicate
    assert res.match_type == DuplicateMatchType.EXACT_IDENTITY
    assert "DOC-PRIOR-001" in res.matching_document_ids
    assert disc is not None
    assert disc.rule_id == "DUP_001"
    assert disc.outcome == ValidationOutcome.FAIL
    assert disc.severity == Severity.HIGH


@pytest.mark.unit
def test_duplicate_across_different_vendors(prior_record: InvoiceExtractionRecord) -> None:
    """Verify same invoice number across different vendors triggers DUP_003 warning."""
    detector = DuplicateDetector(historical_records=[prior_record])

    candidate = InvoiceExtractionRecord(
        document_id="DOC-CAND-003",
        file_name="diff_vendor.pdf",
        raw_fields={
            "invoice_number": "INV-2024-9999",  # Identical ID
            "vendor_name": "Delta Office Furnishings Co.",  # Different vendor
            "invoice_date": date(2024, 6, 5),
            "total": Decimal("750.00"),
        },
    )

    res, disc = detector.check_duplicate(candidate)
    assert res.is_duplicate
    assert res.match_type == DuplicateMatchType.POTENTIAL_MATCH
    assert disc is not None
    assert disc.rule_id == "DUP_003"
    assert disc.outcome == ValidationOutcome.WARNING
    assert disc.severity == Severity.MEDIUM


@pytest.mark.unit
def test_distinct_invoices_not_flagged(prior_record: InvoiceExtractionRecord) -> None:
    """Verify distinct invoices from the same vendor across different months are not flagged."""
    detector = DuplicateDetector(historical_records=[prior_record])

    candidate = InvoiceExtractionRecord(
        document_id="DOC-CAND-004",
        file_name="monthly_bill.pdf",
        raw_fields={
            "invoice_number": "INV-2024-1000",  # Distinct
            "vendor_name": "Apex Cloud Systems Inc.",
            "invoice_date": date(2024, 11, 1),  # 5 months later
            "total": Decimal("500.00"),  # Same recurring fee
        },
    )

    res, disc = detector.check_duplicate(candidate)
    assert not res.is_duplicate
    assert res.match_type == DuplicateMatchType.NONE
    assert disc is None
