"""End-to-end integration test verifying complete application workflow.

Tests: Upload/Ingest -> Extraction -> Validation -> Review Workbench -> Correction -> Revalidation -> Approval -> Audit -> Export.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from app.services.state import AppState

from documind.exceptions import UnresolvedDiscrepancyError
from documind.reporting.exporters import (
    AuditHistoryExporter,
    DiscrepancyReportExporter,
    ProcessingSummaryExporter,
    ReviewOutcomeExporter,
)
from documind.review.models import ReviewStatus
from documind.validation.models import OverallValidationStatus


@pytest.mark.integration
def test_full_application_workflow_end_to_end(tmp_path: Path) -> None:
    state = AppState(persistence_dir=tmp_path)

    # 1. Ingest clean invoice (DOC-SYN-001)
    pdf_001 = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    ok1, msg1, doc_id1 = state.process_document_bytes(
        pdf_001.read_bytes(), "syn_invoice_001_digital.pdf"
    )
    assert ok1 is True and doc_id1 is not None
    assert state.validations[doc_id1].overall_status == OverallValidationStatus.VALID

    # 2. Ingest missing invoice number invoice (DOC-SYN-007)
    pdf_007 = Path("data/synthetic_documents/syn_invoice_007_digital.pdf")
    ok7, msg7, doc_id7 = state.process_document_bytes(
        pdf_007.read_bytes(), "syn_invoice_007_digital.pdf"
    )
    assert ok7 is True and doc_id7 is not None
    assert state.validations[doc_id7].overall_status == OverallValidationStatus.INVALID

    # 3. Ingest arithmetic mismatch invoice (DOC-SYN-015)
    pdf_015 = Path("data/synthetic_documents/syn_invoice_015_digital.pdf")
    ok15, msg15, doc_id15 = state.process_document_bytes(
        pdf_015.read_bytes(), "syn_invoice_015_digital.pdf"
    )
    assert ok15 is True and doc_id15 is not None
    assert state.validations[doc_id15].overall_status == OverallValidationStatus.NEEDS_REVIEW

    # 4. Review & approve clean invoice (DOC-SYN-001)
    rev1 = state.review_service.get_active_review_for_document(doc_id1)
    assert rev1.status == ReviewStatus.PENDING
    state.review_service.start_review(rev1.review_id, reviewer="reviewer_bob")
    appr1 = state.review_service.approve_document(
        rev1.review_id, reviewer="reviewer_bob", reason_code="VERIFIED"
    )
    assert appr1.status == ReviewStatus.APPROVED

    # 5. Review missing invoice number (DOC-SYN-007): verify approval gateway blocks
    rev7 = state.review_service.get_active_review_for_document(doc_id7)
    state.review_service.start_review(rev7.review_id, reviewer="reviewer_alice")
    with pytest.raises(UnresolvedDiscrepancyError):
        state.review_service.approve_document(rev7.review_id, reviewer="reviewer_alice")

    # Correct missing invoice number
    corr7 = state.review_service.submit_correction(
        review_id=rev7.review_id,
        field_name="invoice_number",
        corrected_value="INV-2024-MANUAL-007",
        reason="Supplied by supplier via confirmed PO",
        reviewer="reviewer_alice",
        is_reviewer_supplied=True,
        auto_accept=True,
    )
    assert corr7.is_reviewer_supplied is True

    # Re-validation gateway check on corrected view -> now VALID
    rev7_updated = state.review_service.get_review(rev7.review_id)
    assert rev7_updated.corrected_view is not None
    assert (
        rev7_updated.corrected_view.corrected_validation_result.overall_status
        == OverallValidationStatus.VALID
    )

    # Now approve DOC-SYN-007
    appr7 = state.review_service.approve_document(
        rev7.review_id, reviewer="reviewer_alice", reason_code="CORRECTED"
    )
    assert appr7.status == ReviewStatus.APPROVED

    # 6. Review arithmetic mismatch (DOC-SYN-015): verify approval gateway blocks
    rev15 = state.review_service.get_active_review_for_document(doc_id15)
    state.review_service.start_review(rev15.review_id, reviewer="reviewer_dan")
    with pytest.raises(UnresolvedDiscrepancyError):
        state.review_service.approve_document(rev15.review_id, reviewer="reviewer_dan")

    # Correct total to 1716.00 (1560 subtotal + 156 tax)
    state.review_service.submit_correction(
        review_id=rev15.review_id,
        field_name="total",
        corrected_value=Decimal("1716.00"),
        reason="Correcting calculation to 1716.00",
        reviewer="reviewer_dan",
        evidence_references=["total"],
        auto_accept=True,
    )
    appr15 = state.review_service.approve_document(
        rev15.review_id, reviewer="reviewer_dan", reason_code="CORRECTED_MATH"
    )
    assert appr15.status == ReviewStatus.APPROVED

    # 7. Test Export Reporting
    exts = list(state.extractions.values())
    vals = list(state.validations.values())
    revs = state.review_service.list_reviews()
    evts = state.audit_trail.get_events()

    # CSV Exporters
    csv_proc = ProcessingSummaryExporter.to_csv(exts, vals, revs)
    assert doc_id1 in csv_proc
    assert doc_id7 in csv_proc
    assert doc_id15 in csv_proc

    csv_disc = DiscrepancyReportExporter.to_csv(vals)
    assert "BIZ_001" in csv_disc
    assert "ARITH_003" in csv_disc

    csv_revs = ReviewOutcomeExporter.to_csv(revs)
    assert "APPROVED" in csv_revs

    csv_aud = AuditHistoryExporter.to_csv(evts)
    assert "DOCUMENT_APPROVED" in csv_aud
    assert "CORRECTION_ACCEPTED" in csv_aud
