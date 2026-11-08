"""Domain models for the human review workflow, decisions, corrections, and lifecycle.

Defines Pydantic models and explicit state machine rules governing reviewer interactions,
field-level corrections, and document approval gateways.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from documind.schemas.invoice import InvoiceData
from documind.validation.models import OverallValidationStatus, ValidationResult


class ReviewStatus(str, Enum):
    """Lifecycle states for human review of an extracted document."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETURNED_FOR_REVIEW = "RETURNED_FOR_REVIEW"


PERMITTED_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.PENDING: {
        ReviewStatus.IN_REVIEW,
        ReviewStatus.REJECTED,
    },
    ReviewStatus.IN_REVIEW: {
        ReviewStatus.CORRECTION_REQUESTED,
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.RETURNED_FOR_REVIEW,
    },
    ReviewStatus.CORRECTION_REQUESTED: {
        ReviewStatus.IN_REVIEW,
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.RETURNED_FOR_REVIEW,
    },
    ReviewStatus.RETURNED_FOR_REVIEW: {
        ReviewStatus.IN_REVIEW,
        ReviewStatus.REJECTED,
    },
    ReviewStatus.APPROVED: {
        ReviewStatus.RETURNED_FOR_REVIEW,  # Re-review initiated
    },
    ReviewStatus.REJECTED: {
        ReviewStatus.RETURNED_FOR_REVIEW,  # Re-review initiated
    },
}


class ReviewDecisionType(str, Enum):
    """Permitted decision actions submitted by a human reviewer."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CORRECTION = "REQUEST_CORRECTION"
    CORRECT_AND_APPROVE = "CORRECT_AND_APPROVE"
    RETURN_FOR_REVIEW = "RETURN_FOR_REVIEW"


class CorrectionStatus(str, Enum):
    """Status of an individual field-level correction proposal."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class FieldCorrection(BaseModel):
    """Representation of a reviewer-proposed correction to an extracted invoice field."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    correction_id: str = Field(
        default_factory=lambda: f"CORR-{uuid.uuid4().hex[:8].upper()}",
        description="Unique identifier for this correction",
    )
    field_name: str = Field(..., description="Canonical invoice field being corrected")
    original_value: Any = Field(
        default=None, description="Original extracted value from the document"
    )
    corrected_value: Any = Field(..., description="Reviewer-proposed new value")
    reason: str = Field(
        ..., min_length=3, description="Reviewer rationale explaining the correction"
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="Identifiers/keys of supporting FieldEvidence tokens if document-grounded",
    )
    reviewer: str = Field(..., description="Identity of the reviewer proposing the correction")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when correction was submitted",
    )
    status: CorrectionStatus = Field(
        default=CorrectionStatus.PROPOSED, description="Current lifecycle state of the correction"
    )
    is_reviewer_supplied: bool = Field(
        default=False,
        description="True if manually supplied without source document bounding box evidence",
    )
    reviewed_by: str | None = Field(
        default=None, description="Identity of reviewer/approver who accepted/rejected"
    )
    reviewed_at: datetime | None = Field(
        default=None, description="Timestamp of acceptance/rejection"
    )
    rejection_reason: str | None = Field(
        default=None, description="Explanation if correction was rejected"
    )


class ReviewDecision(BaseModel):
    """Audit record of a reviewer decision submitted on a review record."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(
        default_factory=lambda: f"DEC-{uuid.uuid4().hex[:8].upper()}",
        description="Unique identifier for this decision",
    )
    decision_type: ReviewDecisionType = Field(..., description="Type of decision submitted")
    reviewer: str = Field(..., description="Reviewer user identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Submission timestamp"
    )
    reason_code: str = Field(
        ..., description="Standardized reason code (e.g. APPROVED_CLEAN, REJECTED_DUPLICATE)"
    )
    comment: str | None = Field(default=None, description="Optional narrative comments")
    discrepancy_ids: list[str] = Field(
        default_factory=list, description="IDs of discrepancies addressed or resolved"
    )
    affected_fields: list[str] = Field(
        default_factory=list, description="Invoice fields affected by this decision"
    )
    evidence_ids: list[str] = Field(
        default_factory=list, description="Referenced evidence keys supporting the decision"
    )


class CorrectedDocumentView(BaseModel):
    """Separate, non-destructive presentation of an invoice incorporating accepted corrections."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    document_id: str = Field(..., description="Document identifier")
    effective_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Merged representation: original raw fields overlaid with accepted corrections",
    )
    effective_data: InvoiceData | None = Field(
        default=None,
        description="Re-parsed InvoiceData structure using accepted corrections",
    )
    accepted_corrections: list[FieldCorrection] = Field(
        default_factory=list, description="All accepted corrections currently active"
    )
    corrected_validation_result: ValidationResult | None = Field(
        default=None,
        description="Phase 5 validation result evaluated against the corrected document state",
    )


class ReviewRecord(BaseModel):
    """Master human review record tracking document review lifecycle, corrections, and decisions."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    review_id: str = Field(
        default_factory=lambda: f"REV-{uuid.uuid4().hex[:8].upper()}",
        description="Unique identifier for this review instance",
    )
    document_id: str = Field(..., description="Referenced document identifier")
    extraction_reference: str = Field(
        ..., description="Reference/hash identifying the source extraction version"
    )
    validation_result_id: str | None = Field(
        default=None, description="Reference to initial Phase 5 validation report"
    )
    initial_validation_status: OverallValidationStatus = Field(
        ..., description="Original validation outcome prior to human review"
    )
    status: ReviewStatus = Field(default=ReviewStatus.PENDING, description="Current workflow state")
    assigned_reviewer: str | None = Field(
        default=None, description="Assigned reviewer user identifier"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last modification timestamp"
    )
    completed_at: datetime | None = Field(
        default=None, description="Timestamp when review reached a terminal state"
    )
    revision: int = Field(
        default=1, ge=1, description="Optimistic concurrency revision version counter"
    )
    decisions: list[ReviewDecision] = Field(
        default_factory=list, description="Historical list of review decisions"
    )
    corrections: list[FieldCorrection] = Field(
        default_factory=list, description="All proposed, accepted, and rejected field corrections"
    )
    corrected_view: CorrectedDocumentView | None = Field(
        default=None,
        description="Separate corrected representation of the document if corrections were accepted",
    )
