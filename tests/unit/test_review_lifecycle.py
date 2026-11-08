"""Unit tests verifying the human review lifecycle and state transition rules."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from documind.exceptions import (
    DuplicateActiveReviewError,
    InvalidStateTransitionError,
    ReviewNotFoundError,
    UnresolvedDiscrepancyError,
)
from documind.review.models import ReviewDecisionType, ReviewStatus
from documind.review.service import ReviewService
from documind.schemas.invoice import (
    EvidenceStatus,
    ExtractionMethod,
    FieldEvidence,
    InvoiceData,
    InvoiceExtractionRecord,
)
from documind.validation.models import (
    Discrepancy,
    OverallValidationStatus,
    RuleCategory,
    Severity,
    ValidationOutcome,
    ValidationResult,
)


def _make_dummy_record(
    doc_id: str = "DOC-TEST-001",
    invoice_number: str = "INV-001",
    total: Decimal = Decimal("100.00"),
) -> InvoiceExtractionRecord:
    inv_data = InvoiceData(
        invoice_number=invoice_number,
        invoice_date=date(2024, 1, 1),
        vendor_name="Acme Corp",
        currency="USD",
        total=total,
    )
    raw_fields = {
        "invoice_number": invoice_number,
        "invoice_date": date(2024, 1, 1),
        "vendor_name": "Acme Corp",
        "currency": "USD",
        "total": total,
    }
    evidence = {
        "invoice_number": FieldEvidence(
            raw_text=invoice_number,
            confidence=0.95,
            method=ExtractionMethod.NATIVE_TEXT,
            field_name="invoice_number",
            extracted_value=invoice_number,
            status=EvidenceStatus.EXTRACTED,
        ),
        "total": FieldEvidence(
            raw_text=str(total),
            confidence=0.95,
            method=ExtractionMethod.NATIVE_TEXT,
            field_name="total",
            extracted_value=total,
            status=EvidenceStatus.EXTRACTED,
        ),
    }
    return InvoiceExtractionRecord(
        document_id=doc_id,
        file_name=f"{doc_id}.pdf",
        data=inv_data,
        raw_fields=raw_fields,
        evidence=evidence,
        validation_passed=True,
    )


def _make_dummy_val_result(
    doc_id: str = "DOC-TEST-001",
    status: OverallValidationStatus = OverallValidationStatus.VALID,
    discrepancies: list[Discrepancy] | None = None,
) -> ValidationResult:
    return ValidationResult(
        document_id=doc_id,
        overall_status=status,
        rules_evaluated=19,
        rules_passed=19 if status == OverallValidationStatus.VALID else 18,
        rules_failed=1 if status != OverallValidationStatus.VALID else 0,
        discrepancies=discrepancies or [],
        recommended_action="Ready for approval",
        evaluation_timestamp=datetime.now(UTC),
    )


def test_review_creation() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-001")
    val_res = _make_dummy_val_result("DOC-001")

    review = service.create_review(record, val_res, actor="auditor_alice")
    assert review.review_id.startswith("REV-")
    assert review.document_id == "DOC-001"
    assert review.status == ReviewStatus.PENDING
    assert review.revision == 1
    assert review.assigned_reviewer is None


def test_duplicate_active_review_rejected() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-001")
    val_res = _make_dummy_val_result("DOC-001")

    service.create_review(record, val_res, actor="alice")
    with pytest.raises(DuplicateActiveReviewError):
        service.create_review(record, val_res, actor="bob")


def test_review_initiation_and_assignment() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-002")
    val_res = _make_dummy_val_result("DOC-002")

    review = service.create_review(record, val_res)
    service.assign_reviewer(review.review_id, reviewer="reviewer_bob", actor="supervisor")

    updated = service.get_review(review.review_id)
    assert updated.assigned_reviewer == "reviewer_bob"
    assert updated.revision == 2

    # Start review
    started = service.start_review(review.review_id, reviewer="reviewer_bob")
    assert started.status == ReviewStatus.IN_REVIEW
    assert started.revision == 3


def test_approval_clean_document() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-003")
    val_res = _make_dummy_val_result("DOC-003", OverallValidationStatus.VALID)

    review = service.create_review(record, val_res)
    service.start_review(review.review_id, reviewer="alice")
    approved = service.approve_document(review.review_id, reviewer="alice", reason_code="VERIFIED")

    assert approved.status == ReviewStatus.APPROVED
    assert approved.completed_at is not None
    assert len(approved.decisions) == 1
    assert approved.decisions[0].decision_type == ReviewDecisionType.APPROVE


def test_approval_blocked_on_invalid_status() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-004")
    crit_disc = Discrepancy(
        discrepancy_id="DISC-CRIT",
        document_id="DOC-004",
        rule_id="BIZ_001",
        rule_name="Mandatory Fields",
        category=RuleCategory.COMPLETENESS,
        severity=Severity.CRITICAL,
        outcome=ValidationOutcome.FAIL,
        explanation="Missing invoice number",
    )
    val_res = _make_dummy_val_result(
        "DOC-004", OverallValidationStatus.INVALID, discrepancies=[crit_disc]
    )

    review = service.create_review(record, val_res)
    service.start_review(review.review_id, reviewer="alice")

    with pytest.raises(UnresolvedDiscrepancyError) as exc:
        service.approve_document(review.review_id, reviewer="alice")
    assert "cannot be approved in INVALID validation status" in str(exc.value)


def test_approval_blocked_on_needs_review_without_override() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-005")
    high_disc = Discrepancy(
        discrepancy_id="DISC-HIGH",
        document_id="DOC-005",
        rule_id="ARITH_003",
        rule_name="Arithmetic Mismatch",
        category=RuleCategory.ARITHMETIC,
        severity=Severity.HIGH,
        outcome=ValidationOutcome.FAIL,
        explanation="Total mismatch",
    )
    val_res = _make_dummy_val_result(
        "DOC-005", OverallValidationStatus.NEEDS_REVIEW, discrepancies=[high_disc]
    )

    review = service.create_review(record, val_res)
    service.start_review(review.review_id, reviewer="alice")

    with pytest.raises(UnresolvedDiscrepancyError):
        service.approve_document(review.review_id, reviewer="alice", reason_code="APPROVED_CLEAN")

    # Allowed with explicit OVERRIDE code
    approved = service.approve_document(
        review.review_id,
        reviewer="alice",
        reason_code="OVERRIDE_VERIFIED_BY_FINANCE",
        comment="Discrepancy verified against purchase contract.",
    )
    assert approved.status == ReviewStatus.APPROVED


def test_rejection_lifecycle() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-006")
    val_res = _make_dummy_val_result("DOC-006")

    review = service.create_review(record, val_res)
    service.start_review(review.review_id, reviewer="alice")
    rejected = service.reject_document(
        review.review_id,
        reviewer="alice",
        reason_code="REJECTED_FRAUDULENT",
        comment="Suspicious invoice details.",
    )
    assert rejected.status == ReviewStatus.REJECTED
    assert rejected.completed_at is not None
    assert rejected.decisions[0].decision_type == ReviewDecisionType.REJECT


def test_return_for_review_and_rereview() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-007")
    val_res = _make_dummy_val_result("DOC-007")

    review = service.create_review(record, val_res)
    service.start_review(review.review_id, reviewer="alice")
    service.approve_document(review.review_id, reviewer="alice", reason_code="APPROVED")

    # Re-review initiated on approved document
    returned = service.return_for_review(
        review.review_id,
        reviewer="auditor_lead",
        reason="Auditing vendor invoices per Q4 compliance sweep.",
    )
    assert returned.status == ReviewStatus.RETURNED_FOR_REVIEW
    assert returned.completed_at is None


def test_invalid_state_transitions() -> None:
    service = ReviewService()
    record = _make_dummy_record("DOC-008")
    val_res = _make_dummy_val_result("DOC-008")

    review = service.create_review(record, val_res)
    # Direct PENDING to APPROVED is invalid (must go through IN_REVIEW)
    with pytest.raises(InvalidStateTransitionError):
        service.approve_document(review.review_id, reviewer="alice")


def test_review_not_found() -> None:
    service = ReviewService()
    with pytest.raises(ReviewNotFoundError):
        service.get_review("NONEXISTENT-ID")
