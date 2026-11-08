"""Workflow service orchestrating human review lifecycle, corrections, and audit trails.

Enforces state machines, optimistic concurrency control, verification gateways,
non-destructive field corrections, and re-validation of corrected document representations.
"""

import threading
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from documind.exceptions import (
    DuplicateActiveReviewError,
    InvalidCorrectionError,
    InvalidStateTransitionError,
    ReviewConcurrencyError,
    ReviewError,
    ReviewNotFoundError,
    UnresolvedDiscrepancyError,
)
from documind.review.audit import AuditEventType, AuditTrail
from documind.review.models import (
    PERMITTED_TRANSITIONS,
    CorrectedDocumentView,
    CorrectionStatus,
    FieldCorrection,
    ReviewDecision,
    ReviewDecisionType,
    ReviewRecord,
    ReviewStatus,
)
from documind.schemas.invoice import (
    EvidenceStatus,
    ExtractionMethod,
    FieldEvidence,
    InvoiceData,
    InvoiceExtractionRecord,
)
from documind.validation.models import (
    OverallValidationStatus,
    Severity,
    ValidationResult,
)
from documind.validation.service import ValidationService

UTC = timezone.utc


class ReviewService:
    """Service managing document review workflows, field corrections, and audit history."""

    def __init__(
        self,
        audit_trail: AuditTrail | None = None,
        validation_service: ValidationService | None = None,
    ) -> None:
        self.audit_trail = audit_trail if audit_trail is not None else AuditTrail()
        self.validation_service = (
            validation_service if validation_service is not None else ValidationService()
        )
        self._reviews: dict[str, ReviewRecord] = {}
        self._document_reviews: dict[str, list[str]] = {}  # doc_id -> list of review_ids
        self._extractions: dict[str, InvoiceExtractionRecord] = {}  # doc_id -> extraction
        self._initial_validations: dict[str, ValidationResult] = {}  # doc_id -> validation
        self._lock = threading.Lock()

    def create_review(
        self,
        record: InvoiceExtractionRecord,
        validation_result: ValidationResult,
        actor: str = "system",
        assigned_reviewer: str | None = None,
    ) -> ReviewRecord:
        """Create and register a new review record for an ingested document.

        Args:
            record: Structured extraction record from Phase 4.
            validation_result: Business validation result from Phase 5.
            actor: User or system initiating review creation.
            assigned_reviewer: Optional pre-assigned reviewer identity.

        Returns:
            Newly created ReviewRecord in PENDING status.

        Raises:
            DuplicateActiveReviewError: If an active review already exists for this document.
        """
        doc_id = record.document_id

        with self._lock:
            # Check for existing active review
            existing_review_ids = self._document_reviews.get(doc_id, [])
            for r_id in existing_review_ids:
                prior = self._reviews[r_id]
                if prior.status not in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
                    raise DuplicateActiveReviewError(
                        f"An active review '{r_id}' already exists for document '{doc_id}' "
                        f"in state '{prior.status.value}'."
                    )

            review_id = f"REV-{uuid.uuid4().hex[:8].upper()}"
            review = ReviewRecord(
                review_id=review_id,
                document_id=doc_id,
                extraction_reference=record.file_name,
                validation_result_id=f"VAL-{doc_id}",
                initial_validation_status=validation_result.overall_status,
                status=ReviewStatus.PENDING,
                assigned_reviewer=assigned_reviewer,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                revision=1,
            )

            self._reviews[review_id] = review
            self._document_reviews.setdefault(doc_id, []).append(review_id)
            self._extractions[doc_id] = record
            self._initial_validations[doc_id] = validation_result

        # Record audit event outside lock
        self.audit_trail.record_event(
            document_id=doc_id,
            review_id=review_id,
            event_type=AuditEventType.REVIEW_CREATED,
            actor=actor,
            previous_state=None,
            new_state=ReviewStatus.PENDING.value,
            details={
                "initial_validation_status": validation_result.overall_status.value,
                "discrepancies_count": len(validation_result.discrepancies),
                "assigned_reviewer": assigned_reviewer,
            },
        )

        if assigned_reviewer:
            self.audit_trail.record_event(
                document_id=doc_id,
                review_id=review_id,
                event_type=AuditEventType.REVIEW_ASSIGNED,
                actor=actor,
                new_state=assigned_reviewer,
                details={"assigned_to": assigned_reviewer},
            )

        return review

    def get_review(self, review_id: str) -> ReviewRecord:
        """Retrieve a review record by review ID."""
        with self._lock:
            if review_id not in self._reviews:
                raise ReviewNotFoundError(f"Review record '{review_id}' does not exist.")
            return self._reviews[review_id]

    def get_active_review_for_document(self, document_id: str) -> ReviewRecord | None:
        """Retrieve current active review for a document if one exists."""
        with self._lock:
            review_ids = self._document_reviews.get(document_id, [])
            for r_id in reversed(review_ids):
                r = self._reviews[r_id]
                if r.status not in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
                    return r
            # If all are terminal, return the latest one if exists
            return self._reviews[review_ids[-1]] if review_ids else None

    def get_document_context(
        self, review_id: str
    ) -> tuple[ReviewRecord, InvoiceExtractionRecord, ValidationResult, list[Any]]:
        """Retrieve comprehensive review package for reviewer inspection."""
        review = self.get_review(review_id)
        with self._lock:
            extraction = self._extractions[review.document_id]
            validation = self._initial_validations[review.document_id]
        events = self.audit_trail.get_events_for_review(review_id)
        return review, extraction, validation, events

    def list_reviews(self, status: ReviewStatus | None = None) -> list[ReviewRecord]:
        """List all review records, optionally filtered by status."""
        with self._lock:
            all_reviews = list(self._reviews.values())
        if status is not None:
            return [r for r in all_reviews if r.status == status]
        return all_reviews

    def assign_reviewer(
        self,
        review_id: str,
        reviewer: str,
        actor: str,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Assign or reassign reviewer ownership for a review record."""
        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)

            prev_assignee = review.assigned_reviewer
            review.assigned_reviewer = reviewer
            review.updated_at = datetime.now(UTC)
            review.revision += 1

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.REVIEW_ASSIGNED,
            actor=actor,
            previous_state=prev_assignee,
            new_state=reviewer,
            details={"assigned_reviewer": reviewer},
        )
        return review

    def start_review(
        self,
        review_id: str,
        reviewer: str,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Transition review from PENDING (or resumed) to IN_REVIEW."""
        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)

            prev_status = review.status
            if prev_status == ReviewStatus.IN_REVIEW:
                # Already in review; if same reviewer, idempotent resume
                if review.assigned_reviewer == reviewer:
                    return review
                # Reassignment to another active reviewer
                review.assigned_reviewer = reviewer
                review.updated_at = datetime.now(UTC)
                review.revision += 1
            else:
                self._validate_transition(prev_status, ReviewStatus.IN_REVIEW)
                review.status = ReviewStatus.IN_REVIEW
                review.assigned_reviewer = reviewer
                review.updated_at = datetime.now(UTC)
                review.revision += 1

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.REVIEW_STARTED,
            actor=reviewer,
            previous_state=prev_status.value,
            new_state=ReviewStatus.IN_REVIEW.value,
            details={"reviewer": reviewer},
        )
        return review

    def submit_correction(
        self,
        review_id: str,
        field_name: str,
        corrected_value: Any,
        reason: str,
        reviewer: str,
        evidence_references: list[str] | None = None,
        is_reviewer_supplied: bool = False,
        auto_accept: bool = False,
        expected_revision: int | None = None,
    ) -> FieldCorrection:
        """Propose a field correction, maintaining separation from original extraction."""
        if not reason or len(reason.strip()) < 3:
            raise InvalidCorrectionError(
                "Correction proposal requires a non-empty rationale of at least 3 characters."
            )

        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)

            if review.status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
                raise InvalidStateTransitionError(
                    f"Cannot submit corrections to review '{review_id}' in terminal state '{review.status.value}'."
                )

            extraction = self._extractions[review.document_id]
            orig_val = extraction.raw_fields.get(field_name)

            # Validate evidence references if supplied
            refs = evidence_references or []
            if refs:
                for ref in refs:
                    if ref not in extraction.evidence:
                        raise InvalidCorrectionError(
                            f"Referenced evidence '{ref}' does not exist in extraction evidence for document '{review.document_id}'."
                        )
            else:
                # If no evidence reference provided, explicitly mark as reviewer supplied
                is_reviewer_supplied = True

            # Supersede prior proposed or accepted corrections for this field
            for prior_corr in review.corrections:
                if prior_corr.field_name == field_name and prior_corr.status in {
                    CorrectionStatus.PROPOSED,
                    CorrectionStatus.ACCEPTED,
                }:
                    prior_corr.status = CorrectionStatus.SUPERSEDED

            correction = FieldCorrection(
                field_name=field_name,
                original_value=orig_val,
                corrected_value=corrected_value,
                reason=reason.strip(),
                evidence_references=refs,
                reviewer=reviewer,
                status=CorrectionStatus.ACCEPTED if auto_accept else CorrectionStatus.PROPOSED,
                is_reviewer_supplied=is_reviewer_supplied,
                reviewed_by=reviewer if auto_accept else None,
                reviewed_at=datetime.now(UTC) if auto_accept else None,
            )

            review.corrections.append(correction)
            review.updated_at = datetime.now(UTC)
            review.revision += 1

            if auto_accept:
                self._rebuild_corrected_view_locked(review)

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.CORRECTION_PROPOSED,
            actor=reviewer,
            affected_fields=[field_name],
            details={
                "correction_id": correction.correction_id,
                "field_name": field_name,
                "original_value": str(orig_val),
                "corrected_value": str(corrected_value),
                "reason": reason,
                "is_reviewer_supplied": is_reviewer_supplied,
                "auto_accept": auto_accept,
            },
        )

        if auto_accept:
            self.audit_trail.record_event(
                document_id=review.document_id,
                review_id=review_id,
                event_type=AuditEventType.CORRECTION_ACCEPTED,
                actor=reviewer,
                affected_fields=[field_name],
                details={"correction_id": correction.correction_id},
            )

        return correction

    def accept_correction(
        self,
        review_id: str,
        correction_id: str,
        reviewer: str,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Accept a proposed field correction and trigger validation rerun on corrected view."""
        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)

            target_corr = next(
                (c for c in review.corrections if c.correction_id == correction_id), None
            )
            if not target_corr:
                raise ReviewError(
                    f"Correction '{correction_id}' not found in review '{review_id}'."
                )

            if target_corr.status == CorrectionStatus.ACCEPTED:
                return review

            target_corr.status = CorrectionStatus.ACCEPTED
            target_corr.reviewed_by = reviewer
            target_corr.reviewed_at = datetime.now(UTC)

            # Rebuild corrected document representation and re-run Phase 5 validation
            self._rebuild_corrected_view_locked(review)

            review.updated_at = datetime.now(UTC)
            review.revision += 1

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.CORRECTION_ACCEPTED,
            actor=reviewer,
            affected_fields=[target_corr.field_name],
            details={
                "correction_id": correction_id,
                "field_name": target_corr.field_name,
                "corrected_value": str(target_corr.corrected_value),
            },
        )
        return review

    def reject_correction(
        self,
        review_id: str,
        correction_id: str,
        reviewer: str,
        rejection_reason: str,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Reject a proposed field correction without altering document view."""
        if not rejection_reason or len(rejection_reason.strip()) < 3:
            raise InvalidCorrectionError(
                "Correction rejection requires a valid reason of at least 3 characters."
            )

        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)

            target_corr = next(
                (c for c in review.corrections if c.correction_id == correction_id), None
            )
            if not target_corr:
                raise ReviewError(
                    f"Correction '{correction_id}' not found in review '{review_id}'."
                )

            target_corr.status = CorrectionStatus.REJECTED
            target_corr.reviewed_by = reviewer
            target_corr.reviewed_at = datetime.now(UTC)
            target_corr.rejection_reason = rejection_reason.strip()

            # If it was previously accepted, re-evaluate view
            self._rebuild_corrected_view_locked(review)

            review.updated_at = datetime.now(UTC)
            review.revision += 1

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.CORRECTION_REJECTED,
            actor=reviewer,
            affected_fields=[target_corr.field_name],
            details={
                "correction_id": correction_id,
                "field_name": target_corr.field_name,
                "rejection_reason": rejection_reason,
            },
        )
        return review

    def request_correction(
        self,
        review_id: str,
        reviewer: str,
        reason: str,
        affected_fields: list[str] | None = None,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Transition review state to CORRECTION_REQUESTED."""
        if not reason or not reason.strip():
            raise ReviewError("A non-empty reason is required to request correction.")

        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)
            prev_status = review.status

            self._validate_transition(prev_status, ReviewStatus.CORRECTION_REQUESTED)
            review.status = ReviewStatus.CORRECTION_REQUESTED
            review.updated_at = datetime.now(UTC)
            review.revision += 1

            decision = ReviewDecision(
                decision_type=ReviewDecisionType.REQUEST_CORRECTION,
                reviewer=reviewer,
                reason_code="CORRECTION_REQUESTED",
                comment=reason,
                affected_fields=affected_fields or [],
            )
            review.decisions.append(decision)

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.DECISION_SUBMITTED,
            actor=reviewer,
            previous_state=prev_status.value,
            new_state=ReviewStatus.CORRECTION_REQUESTED.value,
            affected_fields=affected_fields or [],
            comment=reason,
        )
        return review

    def approve_document(
        self,
        review_id: str,
        reviewer: str,
        reason_code: str = "APPROVED_CLEAN",
        comment: str | None = None,
        discrepancy_ids: list[str] | None = None,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Approve a document after verifying all mandatory review gateways are resolved."""
        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)
            prev_status = review.status

            self._validate_transition(prev_status, ReviewStatus.APPROVED)

            # Determine effective validation status
            effective_val: ValidationResult
            if review.corrected_view and review.corrected_view.corrected_validation_result:
                effective_val = review.corrected_view.corrected_validation_result
            else:
                effective_val = self._initial_validations[review.document_id]

            # Gateway 1: Block approval if document is INVALID (missing mandatory fields)
            if effective_val.overall_status == OverallValidationStatus.INVALID:
                critical_rules = [
                    d.rule_id
                    for d in effective_val.discrepancies
                    if d.severity == Severity.CRITICAL
                ]
                raise UnresolvedDiscrepancyError(
                    f"Document '{review.document_id}' cannot be approved in INVALID validation status. "
                    f"Unresolved critical discrepancies: {critical_rules}. "
                    "Reviewer must submit and accept field corrections for mandatory fields."
                )

            # Gateway 2: Block approval if document is INDETERMINATE
            if effective_val.overall_status == OverallValidationStatus.INDETERMINATE:
                raise UnresolvedDiscrepancyError(
                    f"Document '{review.document_id}' cannot be approved in INDETERMINATE validation status. "
                    "Missing core data precludes business validation."
                )

            # Gateway 3: Block approval if NEEDS_REVIEW without explicit approved override or correction
            if effective_val.overall_status == OverallValidationStatus.NEEDS_REVIEW:
                high_discrepancies = [
                    d.rule_id for d in effective_val.discrepancies if d.severity == Severity.HIGH
                ]
                # If high discrepancies exist and reason_code is not an explicit authorized override
                if high_discrepancies and not (
                    reason_code.startswith("OVERRIDE")
                    or reason_code.startswith("ACCEPTED_VARIANCE")
                ):
                    raise UnresolvedDiscrepancyError(
                        f"Document '{review.document_id}' has unresolved HIGH severity discrepancies: {high_discrepancies}. "
                        "Must either submit accepted corrections resolving the discrepancy, or provide an authorized "
                        "OVERRIDE reason code with explanation."
                    )

            review.status = ReviewStatus.APPROVED
            now = datetime.now(UTC)
            review.updated_at = now
            review.completed_at = now
            review.revision += 1

            decision = ReviewDecision(
                decision_type=ReviewDecisionType.APPROVE,
                reviewer=reviewer,
                reason_code=reason_code,
                comment=comment,
                discrepancy_ids=discrepancy_ids or [],
            )
            review.decisions.append(decision)

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.DOCUMENT_APPROVED,
            actor=reviewer,
            previous_state=prev_status.value,
            new_state=ReviewStatus.APPROVED.value,
            details={"reason_code": reason_code},
            comment=comment,
        )
        return review

    def reject_document(
        self,
        review_id: str,
        reviewer: str,
        reason_code: str,
        comment: str | None = None,
        discrepancy_ids: list[str] | None = None,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Reject an invoice document (e.g. duplicate, invalid, or fraudulent submission)."""
        if not reason_code or not reason_code.strip():
            raise ReviewError("A non-empty reason code is required to reject a document.")

        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)
            prev_status = review.status

            self._validate_transition(prev_status, ReviewStatus.REJECTED)

            review.status = ReviewStatus.REJECTED
            now = datetime.now(UTC)
            review.updated_at = now
            review.completed_at = now
            review.revision += 1

            decision = ReviewDecision(
                decision_type=ReviewDecisionType.REJECT,
                reviewer=reviewer,
                reason_code=reason_code,
                comment=comment,
                discrepancy_ids=discrepancy_ids or [],
            )
            review.decisions.append(decision)

        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=AuditEventType.DOCUMENT_REJECTED,
            actor=reviewer,
            previous_state=prev_status.value,
            new_state=ReviewStatus.REJECTED.value,
            details={"reason_code": reason_code},
            comment=comment,
        )
        return review

    def return_for_review(
        self,
        review_id: str,
        reviewer: str,
        reason: str,
        expected_revision: int | None = None,
    ) -> ReviewRecord:
        """Return a document for further review or initiate re-review on a completed document."""
        if not reason or not reason.strip():
            raise ReviewError("A non-empty reason is required to return a document for review.")

        with self._lock:
            review = self._get_review_locked(review_id)
            self._check_concurrency(review, expected_revision)
            prev_status = review.status

            self._validate_transition(prev_status, ReviewStatus.RETURNED_FOR_REVIEW)

            is_rereview = prev_status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}
            review.status = ReviewStatus.RETURNED_FOR_REVIEW
            review.completed_at = None
            review.updated_at = datetime.now(UTC)
            review.revision += 1

            decision = ReviewDecision(
                decision_type=ReviewDecisionType.RETURN_FOR_REVIEW,
                reviewer=reviewer,
                reason_code="REREVIEW" if is_rereview else "RETURNED",
                comment=reason,
            )
            review.decisions.append(decision)

        event_type = (
            AuditEventType.REREVIEW_INITIATED if is_rereview else AuditEventType.REVIEW_RETURNED
        )
        self.audit_trail.record_event(
            document_id=review.document_id,
            review_id=review_id,
            event_type=event_type,
            actor=reviewer,
            previous_state=prev_status.value,
            new_state=ReviewStatus.RETURNED_FOR_REVIEW.value,
            comment=reason,
        )
        return review

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _get_review_locked(self, review_id: str) -> ReviewRecord:
        if review_id not in self._reviews:
            raise ReviewNotFoundError(f"Review record '{review_id}' does not exist.")
        return self._reviews[review_id]

    @staticmethod
    def _check_concurrency(review: ReviewRecord, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != review.revision:
            raise ReviewConcurrencyError(
                f"Concurrency conflict on review '{review.review_id}': expected revision "
                f"{expected_revision}, but current revision is {review.revision}."
            )

    @staticmethod
    def _validate_transition(current: ReviewStatus, target: ReviewStatus) -> None:
        permitted = PERMITTED_TRANSITIONS.get(current, set())
        if target not in permitted:
            raise InvalidStateTransitionError(
                f"Invalid review state transition from '{current.value}' to '{target.value}'. "
                f"Permitted target states: {[s.value for s in permitted]}"
            )

    def _rebuild_corrected_view_locked(self, review: ReviewRecord) -> None:
        """Construct a separate corrected document representation and re-run Phase 5 validation."""
        extraction = self._extractions[review.document_id]
        accepted_corrections = [
            c for c in review.corrections if c.status == CorrectionStatus.ACCEPTED
        ]

        if not accepted_corrections:
            review.corrected_view = None
            return

        effective_fields = dict(extraction.raw_fields)
        corrected_evidence = dict(extraction.evidence)

        financial_fields = {
            "total",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "shipping_amount",
            "amount_paid",
            "balance_due",
            "tax_rate",
        }
        date_fields = {"invoice_date", "due_date"}

        for corr in accepted_corrections:
            val = corr.corrected_value
            # Type normalization for financial & date fields
            if corr.field_name in financial_fields and isinstance(val, (str, int, float)):
                val = Decimal(str(val))
            elif corr.field_name in date_fields and isinstance(val, str):
                val = date.fromisoformat(val)

            effective_fields[corr.field_name] = val

            # Grounding: if reviewer supplied, mark without coordinates; if referenced, preserve
            if corr.is_reviewer_supplied:
                corrected_evidence[corr.field_name] = FieldEvidence(
                    raw_text=str(corr.corrected_value),
                    confidence=1.0,
                    method=ExtractionMethod.HUMAN_CORRECTION,
                    field_name=corr.field_name,
                    extracted_value=val,
                    source_method="human_correction",
                    status=EvidenceStatus.EXTRACTED,
                )

        # Attempt to instantiate InvoiceData with corrected fields
        effective_data: InvoiceData | None = None
        clean_fields = {k: v for k, v in effective_fields.items() if v is not None}
        if "tax_amount" in clean_fields and "tax" not in clean_fields:
            clean_fields["tax"] = clean_fields["tax_amount"]
        if "purchase_order" in clean_fields and "purchase_order_number" not in clean_fields:
            clean_fields["purchase_order_number"] = clean_fields["purchase_order"]

        model_fields = InvoiceData.model_fields.keys()
        valid_model_inputs = {k: v for k, v in clean_fields.items() if k in model_fields}
        try:
            effective_data = InvoiceData(**valid_model_inputs)
        except PydanticValidationError:
            effective_data = None

        # Build simulated corrected extraction record for Phase 5 validation rerun
        simulated_record = InvoiceExtractionRecord(
            document_id=extraction.document_id,
            file_name=extraction.file_name,
            data=effective_data,
            raw_fields=effective_fields,
            evidence=corrected_evidence,
            validation_passed=effective_data is not None,
            validation_errors=[],
            review_status="needs_review",
            warnings=list(extraction.warnings),
        )

        # Re-run Phase 5 validation on the corrected representation
        corrected_val_result = self.validation_service.validate_record(simulated_record)

        review.corrected_view = CorrectedDocumentView(
            document_id=review.document_id,
            effective_fields=effective_fields,
            effective_data=effective_data,
            accepted_corrections=accepted_corrections,
            corrected_validation_result=corrected_val_result,
        )
