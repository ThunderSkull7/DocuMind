"""Unit tests for vendor master and purchase order reference matching."""

from decimal import Decimal

import pytest

from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.models import (
    ReferenceMatchStatus,
    Severity,
    ValidationOutcome,
)
from documind.validation.reference_matching import (
    ReferenceMatcher,
    get_default_po_database,
    get_default_vendor_master,
)


@pytest.fixture
def matcher() -> ReferenceMatcher:
    return ReferenceMatcher(
        vendor_master=get_default_vendor_master(),
        po_database=get_default_po_database(),
    )


@pytest.mark.unit
def test_exact_vendor_and_po_match(matcher: ReferenceMatcher) -> None:
    """Verify clean vendor and purchase order reconciliation."""
    record = InvoiceExtractionRecord(
        document_id="TEST-REF-001",
        file_name="invoice.pdf",
        raw_fields={
            "vendor_name": "Beacon Logistics GmbH",
            "vendor_tax_id": "DE-VAT-194820194",
            "purchase_order_number": "PO-2024-001",
            "total": Decimal("589.05"),
            "currency": "EUR",
        },
    )

    res, discs = matcher.match(record)
    assert res.vendor_match_status == ReferenceMatchStatus.EXACT
    assert res.po_match_status == ReferenceMatchStatus.EXACT
    assert res.matched_vendor_id == "VEND-002"
    assert len(discs) == 0


@pytest.mark.unit
def test_po_amount_conflict(matcher: ReferenceMatcher) -> None:
    """Verify that PO amount variance triggers REF_001 FAIL with HIGH severity."""
    record = InvoiceExtractionRecord(
        document_id="TEST-REF-002",
        file_name="po_conflict.pdf",
        raw_fields={
            "vendor_name": "Beacon Logistics GmbH",
            "purchase_order_number": "PO-2024-001",
            "total": Decimal("750.00"),  # Expected: 589.05
            "currency": "EUR",
        },
    )

    res, discs = matcher.match(record)
    assert res.po_match_status == ReferenceMatchStatus.CONFLICT
    assert any(
        d.rule_id == "REF_001"
        and d.outcome == ValidationOutcome.FAIL
        and d.severity == Severity.HIGH
        for d in discs
    )


@pytest.mark.unit
def test_unregistered_vendor_warning(matcher: ReferenceMatcher) -> None:
    """Verify unregistered vendor entity triggers REF_003 warning."""
    record = InvoiceExtractionRecord(
        document_id="TEST-REF-003",
        file_name="unregistered_vendor.pdf",
        raw_fields={
            "vendor_name": "Unknown Freelancer Inc.",
            "total": Decimal("200.00"),
        },
    )

    res, discs = matcher.match(record)
    assert res.vendor_match_status == ReferenceMatchStatus.NOT_FOUND
    assert any(d.rule_id == "REF_003" for d in discs)


@pytest.mark.unit
def test_vendor_tax_id_conflict(matcher: ReferenceMatcher) -> None:
    """Verify conflicting tax ID for recognized vendor triggers REF_002 warning."""
    record = InvoiceExtractionRecord(
        document_id="TEST-REF-004",
        file_name="tax_conflict.pdf",
        raw_fields={
            "vendor_name": "Beacon Logistics GmbH",
            "vendor_tax_id": "DE-VAT-999999999",  # Conflicting Tax ID
            "total": Decimal("500.00"),
        },
    )

    res, discs = matcher.match(record)
    assert any(d.rule_id == "REF_002" and d.severity == Severity.MEDIUM for d in discs)
