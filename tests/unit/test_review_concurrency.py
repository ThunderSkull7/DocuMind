"""Unit tests verifying optimistic concurrency and revision conflict detection."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from documind.exceptions import ReviewConcurrencyError
from documind.review.service import ReviewService
from documind.schemas.invoice import (
    InvoiceData,
    InvoiceExtractionRecord,
)
from documind.validation.models import (
    OverallValidationStatus,
    ValidationResult,
)

UTC = timezone.utc


def _make_dummy_record(doc_id: str = "DOC-CONC-01") -> InvoiceExtractionRecord:
    inv_data = InvoiceData(
        invoice_number="INV-CONC-01",
        invoice_date=date(2024, 1, 1),
        vendor_name="Acme Corp",
        currency="USD",
        total=Decimal("100.00"),
    )
    return InvoiceExtractionRecord(
        document_id=doc_id,
        file_name=f"{doc_id}.pdf",
        data=inv_data,
        raw_fields={"invoice_number": "INV-CONC-01", "total": Decimal("100.00")},
        evidence={},
        validation_passed=True,
    )


def _make_dummy_val_result(doc_id: str = "DOC-CONC-01") -> ValidationResult:
    return ValidationResult(
        document_id=doc_id,
        overall_status=OverallValidationStatus.VALID,
        rules_evaluated=19,
        rules_passed=19,
        rules_failed=0,
        discrepancies=[],
        recommended_action="Ready",
        evaluation_timestamp=datetime.now(UTC),
    )


def test_optimistic_concurrency_conflict_detected() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-CONC-01")
    val_res = _make_dummy_val_result("DOC-CONC-01")

    review = service.create_review(record, val_res, actor="alice")
    assert review.revision == 1

    # Client A begins review with revision 1 -> revision advances to 2
    service.start_review(review.review_id, reviewer="reviewer_a", expected_revision=1)
    assert review.revision == 2

    # Client B attempts to mutate review expecting stale revision 1 -> Concurrency conflict!
    with pytest.raises(ReviewConcurrencyError) as exc:
        service.submit_correction(
            review_id=review.review_id,
            field_name="total",
            corrected_value=Decimal("105.00"),
            reason="Late adjustment",
            reviewer="reviewer_b",
            expected_revision=1,
        )
    assert "Concurrency conflict" in str(exc.value)
    assert "expected revision 1, but current revision is 2" in str(exc.value)

    # With correct current revision (2), operation succeeds
    service.submit_correction(
        review_id=review.review_id,
        field_name="total",
        corrected_value=Decimal("105.00"),
        reason="Adjustment with proper revision",
        reviewer="reviewer_b",
        expected_revision=2,
    )
    assert review.revision == 3
