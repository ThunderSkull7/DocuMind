"""Human review and audit trail subsystem for DocuMind.

Provides domain models, workflow orchestration, non-destructive field corrections,
verification gateways, and append-only audit event logging for invoice review.
"""

from documind.review.audit import AuditEvent, AuditEventType, AuditTrail
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
from documind.review.service import ReviewService

__all__ = [
    "PERMITTED_TRANSITIONS",
    "AuditEvent",
    "AuditEventType",
    "AuditTrail",
    "CorrectedDocumentView",
    "CorrectionStatus",
    "FieldCorrection",
    "ReviewDecision",
    "ReviewDecisionType",
    "ReviewRecord",
    "ReviewService",
    "ReviewStatus",
]
