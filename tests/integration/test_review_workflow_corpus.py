"""Integration tests verifying human review workflows across synthetic corpus documents."""

from decimal import Decimal
from pathlib import Path

import pytest

from documind.exceptions import UnresolvedDiscrepancyError
from documind.extraction.field_extractor import StructuredInvoiceExtractor
from documind.extraction.service import ExtractionService
from documind.review.models import ReviewStatus
from documind.review.service import ReviewService
from documind.validation.models import OverallValidationStatus
from documind.validation.service import ValidationService


@pytest.fixture(scope="module")
def extraction_service() -> ExtractionService:
    return ExtractionService()


@pytest.fixture(scope="module")
def field_extractor() -> StructuredInvoiceExtractor:
    return StructuredInvoiceExtractor()


@pytest.fixture(scope="module")
def validation_service() -> ValidationService:
    return ValidationService()


@pytest.mark.integration
def test_clean_document_review_and_approval(
    extraction_service: ExtractionService,
    field_extractor: StructuredInvoiceExtractor,
    validation_service: ValidationService,
) -> None:
    """Verify that a clean valid invoice passes straight through review to approval."""
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    raw_res = extraction_service.extract_from_bytes(
        pdf_path.read_bytes(), document_id="DOC-SYN-001"
    )
    record = field_extractor.extract(raw_res, file_name="syn_invoice_001_digital.pdf")
    val_res = validation_service.validate_record(record)
    assert val_res.overall_status == OverallValidationStatus.VALID

    review_service = ReviewService(validation_service=validation_service)
    review = review_service.create_review(record, val_res, actor="ingest_pipeline")
    assert review.status == ReviewStatus.PENDING

    review_service.start_review(review.review_id, reviewer="reviewer_bob")
    approved = review_service.approve_document(
        review.review_id,
        reviewer="reviewer_bob",
        reason_code="VERIFIED_CLEAN",
        comment="All header fields, line items, and taxes match exactly.",
    )
    assert approved.status == ReviewStatus.APPROVED
    assert approved.completed_at is not None


@pytest.mark.integration
def test_missing_field_correction_gateway(
    extraction_service: ExtractionService,
    field_extractor: StructuredInvoiceExtractor,
    validation_service: ValidationService,
) -> None:
    """Verify that DOC-SYN-007 (missing invoice number) is blocked until corrected."""
    pdf_path = Path("data/synthetic_documents/syn_invoice_007_digital.pdf")
    raw_res = extraction_service.extract_from_bytes(
        pdf_path.read_bytes(), document_id="DOC-SYN-007"
    )
    record = field_extractor.extract(raw_res, file_name="syn_invoice_007_digital.pdf")
    val_res = validation_service.validate_record(record)
    assert val_res.overall_status == OverallValidationStatus.INVALID

    review_service = ReviewService(validation_service=validation_service)
    review = review_service.create_review(record, val_res)
    review_service.start_review(review.review_id, reviewer="auditor_jane")

    # 1. Approval attempt must fail because status is INVALID
    with pytest.raises(UnresolvedDiscrepancyError) as exc:
        review_service.approve_document(review.review_id, reviewer="auditor_jane")
    assert "cannot be approved in INVALID validation status" in str(exc.value)

    # 2. Submit reviewer-supplied correction for invoice_number
    corr = review_service.submit_correction(
        review_id=review.review_id,
        field_name="invoice_number",
        corrected_value="INV-2024-MANUAL-007",
        reason="Assigned external AP identifier verified via paper delivery note.",
        reviewer="auditor_jane",
        is_reviewer_supplied=True,
        auto_accept=True,
    )
    assert corr.is_reviewer_supplied is True

    # 3. Validation rerun on corrected view should now resolve INVALID -> VALID
    recheck = review_service.get_review(review.review_id)
    assert recheck.corrected_view is not None
    assert recheck.corrected_view.corrected_validation_result is not None
    assert (
        recheck.corrected_view.corrected_validation_result.overall_status
        == OverallValidationStatus.VALID
    )

    # 4. Approval should now succeed cleanly
    approved = review_service.approve_document(
        review.review_id,
        reviewer="auditor_jane",
        reason_code="CORRECTED_AND_VERIFIED",
    )
    assert approved.status == ReviewStatus.APPROVED


@pytest.mark.integration
def test_arithmetic_mismatch_correction_gateway(
    extraction_service: ExtractionService,
    field_extractor: StructuredInvoiceExtractor,
    validation_service: ValidationService,
) -> None:
    """Verify that DOC-SYN-015 (arithmetic total mismatch) is blocked until corrected."""
    pdf_path = Path("data/synthetic_documents/syn_invoice_015_digital.pdf")
    raw_res = extraction_service.extract_from_bytes(
        pdf_path.read_bytes(), document_id="DOC-SYN-015"
    )
    record = field_extractor.extract(raw_res, file_name="syn_invoice_015_digital.pdf")
    val_res = validation_service.validate_record(record)
    assert val_res.overall_status == OverallValidationStatus.NEEDS_REVIEW

    review_service = ReviewService(validation_service=validation_service)
    review = review_service.create_review(record, val_res)
    review_service.start_review(review.review_id, reviewer="reviewer_dan")

    # 1. Approval without override code fails
    with pytest.raises(UnresolvedDiscrepancyError):
        review_service.approve_document(review.review_id, reviewer="reviewer_dan")

    # 2. Submit correction fixing total to 1716.00 (1560.00 subtotal + 156.00 tax)
    corr = review_service.submit_correction(
        review_id=review.review_id,
        field_name="total",
        corrected_value=Decimal("1716.00"),
        reason="Corrected invoice sum: 1560.00 subtotal + 156.00 tax = 1716.00",
        reviewer="reviewer_dan",
        evidence_references=["total"],
        auto_accept=True,
    )
    assert corr.status.value == "ACCEPTED"

    # 3. Check corrected view re-validation outcome -> VALID
    recheck = review_service.get_review(review.review_id)
    assert (
        recheck.corrected_view.corrected_validation_result.overall_status
        == OverallValidationStatus.VALID
    )

    # 4. Approve document
    approved = review_service.approve_document(
        review.review_id,
        reviewer="reviewer_dan",
        reason_code="CORRECTED_MATH_VERIFIED",
    )
    assert approved.status == ReviewStatus.APPROVED
