# ADR 0006: Human Review Workflow, Non-Destructive Corrections & Append-Only Audit Trail

## Status
Accepted

## Context
Following automated structured extraction (Phase 4) and business validation (Phase 5), invoices requiring human intervention (due to missing mandatory fields, ambiguous dates, arithmetic mismatches, duplicate identifiers, or internal policy compliance) must enter a structured human review queue. 

The review subsystem must allow reviewers to inspect extracted values alongside spatial bounding-box evidence, submit field-level corrections, record decisions, and approve or reject documents. Crucially, the system must maintain strict non-destructive isolation between original extraction data and reviewer-submitted corrections, prevent unauthorized or invalid workflow state transitions, enforce optimistic concurrency against stale updates, and record an append-only audit trail.

## Decisions

1. **Explicit Lifecycle State Machine & Permitted Transitions**:
   Review instances follow an explicit, deterministic finite-state lifecycle:
   - States: `PENDING`, `IN_REVIEW`, `CORRECTION_REQUESTED`, `APPROVED`, `REJECTED`, `RETURNED_FOR_REVIEW`.
   - Permitted transitions are strictly enforced via `PERMITTED_TRANSITIONS`. Illegal transitions raise `InvalidStateTransitionError`.
   - Re-review of terminal documents (`APPROVED` or `REJECTED`) is supported by transitioning to `RETURNED_FOR_REVIEW`, recording a `REREVIEW_INITIATED` audit event.

2. **Non-Destructive Field Correction Isolation**:
   Original extraction records (`InvoiceExtractionRecord`), raw fields, and spatial tokens (`FieldEvidence`) are immutable. 
   - Reviewer-proposed corrections are tracked as separate [`FieldCorrection`](file:///d:/Project/Intelligent%20Document%20Extraction/src/documind/review/models.py) objects (`PROPOSED`, `ACCEPTED`, `REJECTED`, `SUPERSEDED`).
   - Multiple corrections to the same field supersede previous proposals without deleting historical attempts.
   - When corrections are accepted, a distinct [`CorrectedDocumentView`](file:///d:/Project/Intelligent%20Document%20Extraction/src/documind/review/models.py) is synthesized. The original extraction remains accessible for audit comparison.

3. **Re-Validation Gateway on Corrected Views**:
   Whenever a financial, date, or business field is corrected and accepted, the Phase 5 [`ValidationService`](file:///d:/Project/Intelligent%20Document%20Extraction/src/documind/validation/service.py) is re-evaluated against the corrected document representation.
   - Approval Gateways:
     - `INVALID` status (missing mandatory fields like `invoice_number` or `vendor_name`) strictly blocks approval (`UnresolvedDiscrepancyError`). Reviewers must supply missing fields.
     - `INDETERMINATE` status strictly blocks approval.
     - `NEEDS_REVIEW` (e.g. arithmetic mismatch) blocks approval unless accepted corrections resolve the discrepancy, or an explicit authorized `OVERRIDE` reason code is provided.

4. **Honest Evidence Attribution (No Fabricated Evidence)**:
   Field corrections referencing original document text must point to valid existing `FieldEvidence` keys. For reviewer-supplied values without source document backing (e.g. external PO reference or manual invoice number assignment), the system marks `is_reviewer_supplied = True` with `bounding_box = None`. No synthetic or false bounding boxes are fabricated.

5. **Append-Only Audit Trail with Realistic Integrity Guarantees**:
   Every state change, reviewer assignment, decision, and correction event is recorded in an immutable [`AuditTrail`](file:///d:/Project/Intelligent%20Document%20Extraction/src/documind/review/audit.py) using frozen [`AuditEvent`](file:///d:/Project/Intelligent%20Document%20Extraction/src/documind/review/audit.py) models.
   - Direct mutation or deletion of audit events is prohibited. Corrections to prior events require appending a subsequent explanatory event.
   - *Limitation & Guarantee Disclosure*: Immutability is enforced at the domain and application level in Python memory and serialized JSON logs. The system does not claim hardware WORM storage or cryptographic blockchain tamper-proofing against root OS administrators.

6. **Optimistic Concurrency Control**:
   Review records maintain a monotonic `revision: int` counter. State-mutating API operations accept an `expected_revision` parameter; if a stale revision is submitted, the operation is rejected with `ReviewConcurrencyError`. Furthermore, duplicate active reviews for the same document are prevented (`DuplicateActiveReviewError`).

## Consequences
- **Positive**: Complete auditability of human decisions; original document provenance is never lost or corrupted; financial risk is mitigated through automated re-validation gateways; concurrent reviewer conflicts are safely detected.
- **Negative**: Reviewers cannot unilaterally force-approve missing mandatory fields without providing substitute values; multiple corrections generate additional audit events, slightly increasing log size.
