"""Unit tests verifying audit event creation, ordering, immutability, and actor attribution."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from documind.exceptions import InvalidStateTransitionError, ReviewError
from documind.review.audit import AuditEventType, AuditTrail
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


def _make_dummy_record(doc_id: str = "DOC-AUDIT-01") -> InvoiceExtractionRecord:
    inv_data = InvoiceData(
        invoice_number="INV-AUD-01",
        invoice_date=date(2024, 1, 1),
        vendor_name="Acme Corp",
        currency="USD",
        total=Decimal("100.00"),
    )
    return InvoiceExtractionRecord(
        document_id=doc_id,
        file_name=f"{doc_id}.pdf",
        data=inv_data,
        raw_fields={"invoice_number": "INV-AUD-01", "total": Decimal("100.00")},
        evidence={},
        validation_passed=True,
    )


def _make_dummy_val_result(doc_id: str = "DOC-AUDIT-01") -> ValidationResult:
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


def test_audit_event_recording_and_ordering() -> None:
    trail = AuditTrail()
    service = ReviewService(audit_trail=trail)
    record = _make_dummy_record("DOC-AUDIT-01")
    val_res = _make_dummy_val_result("DOC-AUDIT-01")

    # 1. Create review -> REVIEW_CREATED
    review = service.create_review(record, val_res, actor="auditor_ann")

    # 2. Assign reviewer -> REVIEW_ASSIGNED
    service.assign_reviewer(review.review_id, reviewer="reviewer_bob", actor="supervisor")

    # 3. Start review -> REVIEW_STARTED
    service.start_review(review.review_id, reviewer="reviewer_bob")

    # 4. Propose correction -> CORRECTION_PROPOSED
    service.submit_correction(
        review_id=review.review_id,
        field_name="total",
        corrected_value=Decimal("100.00"),
        reason="Confirm matching line items",
        reviewer="reviewer_bob",
    )

    # 5. Approve document -> DOCUMENT_APPROVED
    service.approve_document(review.review_id, reviewer="reviewer_bob", reason_code="VERIFIED")

    events = trail.get_events_for_review(review.review_id)
    assert len(events) == 5
    assert [e.event_type for e in events] == [
        AuditEventType.REVIEW_CREATED,
        AuditEventType.REVIEW_ASSIGNED,
        AuditEventType.REVIEW_STARTED,
        AuditEventType.CORRECTION_PROPOSED,
        AuditEventType.DOCUMENT_APPROVED,
    ]

    # Verify actors and document IDs
    assert events[0].actor == "auditor_ann"
    assert events[1].actor == "supervisor"
    assert events[2].actor == "reviewer_bob"
    for e in events:
        assert e.document_id == "DOC-AUDIT-01"
        assert e.review_id == review.review_id
        assert e.timestamp is not None


def test_audit_event_immutability() -> None:
    trail = AuditTrail()
    event = trail.record_event(
        document_id="DOC-01",
        review_id="REV-01",
        event_type=AuditEventType.REVIEW_CREATED,
        actor="alice",
    )

    # Frozen pydantic model should reject direct attribute mutation
    with pytest.raises((PydanticValidationError, TypeError)):
        event.actor = "bob"  # type: ignore


def test_audit_requires_non_empty_actor() -> None:
    trail = AuditTrail()
    with pytest.raises(ReviewError):
        trail.record_event(
            document_id="DOC-01",
            review_id="REV-01",
            event_type=AuditEventType.REVIEW_CREATED,
            actor="",
        )


def test_failed_operation_does_not_produce_misleading_audit_event() -> None:
    trail = AuditTrail()
    service = ReviewService(audit_trail=trail)
    record = _make_dummy_record("DOC-AUDIT-02")
    val_res = _make_dummy_val_result("DOC-AUDIT-02")

    review = service.create_review(record, val_res, actor="alice")
    initial_count = len(trail.get_events())

    # Try invalid transition directly to APPROVED from PENDING
    with pytest.raises(InvalidStateTransitionError):
        service.approve_document(review.review_id, reviewer="alice")

    # Audit trail should have no new events
    assert len(trail.get_events()) == initial_count
