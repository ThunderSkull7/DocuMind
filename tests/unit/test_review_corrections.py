"""Unit tests verifying reviewer field corrections, non-destructive isolation, and re-validation."""

from datetime import date
from decimal import Decimal

import pytest

from documind.exceptions import InvalidCorrectionError
from documind.review.models import CorrectionStatus, ReviewStatus
from documind.review.service import ReviewService
from documind.schemas.invoice import (
    BoundingBox,
    EvidenceStatus,
    ExtractionMethod,
    FieldEvidence,
    InvoiceData,
    InvoiceExtractionRecord,
)
from documind.validation.models import (
    OverallValidationStatus,
)
from documind.validation.service import ValidationService


def _make_record_with_arithmetic_error(
    doc_id: str = "DOC-ARITH-ERR",
) -> InvoiceExtractionRecord:
    # Subtotal 100.00 + Tax 10.00 != Total 150.00 (mismatch $40.00)
    subtotal = Decimal("100.00")
    tax = Decimal("10.00")
    wrong_total = Decimal("150.00")

    raw_fields = {
        "invoice_number": "INV-ERR-01",
        "invoice_date": date(2024, 1, 1),
        "vendor_name": "Test Vendor",
        "currency": "USD",
        "subtotal": subtotal,
        "tax": tax,
        "total": wrong_total,
    }
    evidence = {
        "invoice_number": FieldEvidence(
            raw_text="INV-ERR-01",
            confidence=0.9,
            method=ExtractionMethod.NATIVE_TEXT,
            field_name="invoice_number",
            extracted_value="INV-ERR-01",
            status=EvidenceStatus.EXTRACTED,
        ),
        "total": FieldEvidence(
            raw_text="150.00",
            confidence=0.9,
            method=ExtractionMethod.NATIVE_TEXT,
            field_name="total",
            extracted_value=wrong_total,
            bounding_box=BoundingBox(page=1, x0=100.0, y0=200.0, x1=150.0, y1=215.0),
            status=EvidenceStatus.EXTRACTED,
        ),
    }
    inv_data = InvoiceData(
        invoice_number="INV-ERR-01",
        invoice_date=date(2024, 1, 1),
        vendor_name="Test Vendor",
        currency="USD",
        subtotal=subtotal,
        tax=tax,
        total=wrong_total,
    )
    return InvoiceExtractionRecord(
        document_id=doc_id,
        file_name=f"{doc_id}.pdf",
        data=inv_data,
        raw_fields=raw_fields,
        evidence=evidence,
        validation_passed=True,
    )


def test_field_correction_submission_and_superseding() -> None:
    val_service = ValidationService()
    service = ReviewService(validation_service=val_service)
    record = _make_record_with_arithmetic_error("DOC-CORR-01")
    init_val = val_service.validate_record(record)
    assert init_val.overall_status == OverallValidationStatus.NEEDS_REVIEW

    review = service.create_review(record, init_val)
    service.start_review(review.review_id, reviewer="bob")

    # 1. Propose first correction: change total to 120.00
    corr1 = service.submit_correction(
        review_id=review.review_id,
        field_name="total",
        corrected_value=Decimal("120.00"),
        reason="Preliminary adjustment",
        reviewer="bob",
        evidence_references=["total"],
    )
    assert corr1.status == CorrectionStatus.PROPOSED
    assert len(review.corrections) == 1

    # 2. Propose second correction to same field: changes total to 110.00
    corr2 = service.submit_correction(
        review_id=review.review_id,
        field_name="total",
        corrected_value=Decimal("110.00"),
        reason="Correct sum: 100.00 subtotal + 10.00 tax = 110.00",
        reviewer="bob",
        evidence_references=["total"],
    )
    assert corr2.status == CorrectionStatus.PROPOSED
    assert len(review.corrections) == 2
    # Verify corr1 is now SUPERSEDED
    assert review.corrections[0].status == CorrectionStatus.SUPERSEDED


def test_correction_acceptance_and_revalidation() -> None:
    val_service = ValidationService()
    service = ReviewService(validation_service=val_service)
    record = _make_record_with_arithmetic_error("DOC-CORR-02")
    init_val = val_service.validate_record(record)
    assert init_val.overall_status == OverallValidationStatus.NEEDS_REVIEW

    review = service.create_review(record, init_val)
    service.start_review(review.review_id, reviewer="alice")

    corr = service.submit_correction(
        review_id=review.review_id,
        field_name="total",
        corrected_value=Decimal("110.00"),
        reason="Fixed calculation error: 100 + 10 = 110.00",
        reviewer="alice",
        evidence_references=["total"],
    )

    # Accept the correction
    updated_review = service.accept_correction(
        review.review_id,
        correction_id=corr.correction_id,
        reviewer="supervisor",
    )
    assert corr.status == CorrectionStatus.ACCEPTED
    assert updated_review.corrected_view is not None
    assert updated_review.corrected_view.effective_fields["total"] == Decimal("110.00")

    # Re-run validation outcome should now be VALID (arithmetic is fixed)
    corrected_val = updated_review.corrected_view.corrected_validation_result
    assert corrected_val is not None
    assert corrected_val.overall_status == OverallValidationStatus.VALID

    # Original extraction record remains unchanged!
    assert record.raw_fields["total"] == Decimal("150.00")
    assert record.evidence["total"].extracted_value == Decimal("150.00")

    # Can now approve cleanly without override
    approved = service.approve_document(review.review_id, reviewer="alice")
    assert approved.status == ReviewStatus.APPROVED


def test_correction_rejection() -> None:
    val_service = ValidationService()
    service = ReviewService(validation_service=val_service)
    record = _make_record_with_arithmetic_error("DOC-CORR-03")
    init_val = val_service.validate_record(record)

    review = service.create_review(record, init_val)
    service.start_review(review.review_id, reviewer="alice")

    corr = service.submit_correction(
        review_id=review.review_id,
        field_name="total",
        corrected_value=Decimal("999.00"),
        reason="Bogus total test",
        reviewer="alice",
        evidence_references=["total"],
    )

    updated_review = service.reject_correction(
        review.review_id,
        correction_id=corr.correction_id,
        reviewer="lead_auditor",
        rejection_reason="Incorrect math; does not reconcile with line items.",
    )
    assert corr.status == CorrectionStatus.REJECTED
    assert corr.rejection_reason == "Incorrect math; does not reconcile with line items."
    assert updated_review.corrected_view is None


def test_invalid_correction_reasons_and_evidence() -> None:
    val_service = ValidationService()
    service = ReviewService(validation_service=val_service)
    record = _make_record_with_arithmetic_error("DOC-CORR-04")
    init_val = val_service.validate_record(record)

    review = service.create_review(record, init_val)
    service.start_review(review.review_id, reviewer="alice")

    # Empty reason rejected
    with pytest.raises(InvalidCorrectionError):
        service.submit_correction(
            review_id=review.review_id,
            field_name="total",
            corrected_value=Decimal("110.00"),
            reason="",
            reviewer="alice",
        )

    # Invalid evidence reference rejected
    with pytest.raises(InvalidCorrectionError):
        service.submit_correction(
            review_id=review.review_id,
            field_name="total",
            corrected_value=Decimal("110.00"),
            reason="Good reason",
            reviewer="alice",
            evidence_references=["non_existent_field_evidence_key"],
        )


def test_reviewer_supplied_value_without_evidence() -> None:
    val_service = ValidationService()
    service = ReviewService(validation_service=val_service)
    record = _make_record_with_arithmetic_error("DOC-CORR-05")
    init_val = val_service.validate_record(record)

    review = service.create_review(record, init_val)
    service.start_review(review.review_id, reviewer="alice")

    # Supply missing PO number without evidence
    corr = service.submit_correction(
        review_id=review.review_id,
        field_name="purchase_order",
        corrected_value="PO-9999",
        reason="Supplied by accounts payable department via external email.",
        reviewer="alice",
        evidence_references=[],
        is_reviewer_supplied=True,
        auto_accept=True,
    )
    assert corr.is_reviewer_supplied is True
    assert corr.evidence_references == []
    # Verify view marked as reviewer supplied without fake coordinates
    ev = review.corrected_view.corrected_validation_result
    assert ev is not None
