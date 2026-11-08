"""Append-only audit trail mechanism for DocuMind review workflows.

Maintains an immutable historical sequence of human decisions, correction submissions,
state transitions, and reviewer assignments with actor attribution and timestamps.
"""

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from documind.exceptions import ReviewError

UTC = timezone.utc


class AuditEventType(str, Enum):
    """Categorization of audit events recorded in review workflows."""

    REVIEW_CREATED = "REVIEW_CREATED"
    REVIEW_ASSIGNED = "REVIEW_ASSIGNED"
    REVIEW_STARTED = "REVIEW_STARTED"
    DECISION_SUBMITTED = "DECISION_SUBMITTED"
    CORRECTION_PROPOSED = "CORRECTION_PROPOSED"
    CORRECTION_ACCEPTED = "CORRECTION_ACCEPTED"
    CORRECTION_REJECTED = "CORRECTION_REJECTED"
    REVIEW_RETURNED = "REVIEW_RETURNED"
    DOCUMENT_APPROVED = "DOCUMENT_APPROVED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    REREVIEW_INITIATED = "REREVIEW_INITIATED"


class AuditEvent(BaseModel):
    """Immutable audit event capturing a review workflow state change or action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(
        default_factory=lambda: f"EVT-{uuid.uuid4().hex[:10].upper()}",
        description="Unique event identifier",
    )
    document_id: str = Field(..., description="Document associated with this event")
    review_id: str = Field(..., description="Review instance identifier")
    event_type: AuditEventType = Field(..., description="Audit event category")
    actor: str = Field(..., description="User, reviewer, or automated system initiating action")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when event was recorded",
    )
    previous_state: str | None = Field(
        default=None, description="Previous review status or value prior to this event"
    )
    new_state: str | None = Field(
        default=None, description="New review status or value established by this event"
    )
    affected_fields: list[str] = Field(
        default_factory=list, description="Schema fields affected by this event"
    )
    discrepancy_ids: list[str] = Field(
        default_factory=list, description="IDs of discrepancies referenced or resolved"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Structured contextual metadata"
    )
    comment: str | None = Field(default=None, description="Reviewer comments or explanations")


class AuditTrail:
    """Append-only audit trail storing review workflow events.

    Guarantees:
    - Events are strictly append-only.
    - Historical events cannot be edited, replaced, or deleted through API methods.
    - If an event was recorded in error, a subsequent corrective event must be appended.

    Limitations:
    - In-memory and application-level append enforcement. Does not provide hardware WORM
      (Write Once Read Many) or cryptographic blockchain tamper-proofing against host OS tampering.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def record_event(
        self,
        document_id: str,
        review_id: str,
        event_type: AuditEventType,
        actor: str,
        previous_state: str | None = None,
        new_state: str | None = None,
        affected_fields: list[str] | None = None,
        discrepancy_ids: list[str] | None = None,
        details: dict[str, Any] | None = None,
        comment: str | None = None,
    ) -> AuditEvent:
        """Create and append an immutable audit event."""
        if not actor or not actor.strip():
            raise ReviewError("Audit events require a non-empty actor identifier.")

        event = AuditEvent(
            document_id=document_id,
            review_id=review_id,
            event_type=event_type,
            actor=actor.strip(),
            previous_state=previous_state,
            new_state=new_state,
            affected_fields=affected_fields or [],
            discrepancy_ids=discrepancy_ids or [],
            details=details or {},
            comment=comment,
        )

        with self._lock:
            self._events.append(event)

        return event

    def get_events(self) -> list[AuditEvent]:
        """Return a read-only snapshot copy of all recorded audit events."""
        with self._lock:
            return list(self._events)

    def get_events_for_document(self, document_id: str) -> list[AuditEvent]:
        """Retrieve chronological audit events for a specific document."""
        with self._lock:
            return [e for e in self._events if e.document_id == document_id]

    def get_events_for_review(self, review_id: str) -> list[AuditEvent]:
        """Retrieve chronological audit events for a specific review instance."""
        with self._lock:
            return [e for e in self._events if e.review_id == review_id]

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def __bool__(self) -> bool:
        return True
