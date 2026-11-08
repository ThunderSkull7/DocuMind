"""Unit tests verifying reporting exporters and CSV formula-injection sanitization."""

import json
from datetime import date, datetime, timezone
from decimal import Decimal

from documind.reporting.csv_sanitizer import sanitize_csv_value
from documind.reporting.exporters import (
    AuditHistoryExporter,
    CorrectionHistoryExporter,
    DiscrepancyReportExporter,
    ProcessingSummaryExporter,
    ReviewOutcomeExporter,
)
from documind.review.audit import AuditEvent, AuditEventType
from documind.review.models import (
    CorrectionStatus,
    FieldCorrection,
    ReviewDecision,
    ReviewDecisionType,
    ReviewRecord,
    ReviewStatus,
)
from documind.schemas.invoice import (
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

UTC = timezone.utc


def test_csv_formula_injection_sanitization() -> None:
    # Test formula triggers
    assert sanitize_csv_value("=1+1") == "'=1+1"
    assert sanitize_csv_value("+CMD|' /C calc'!A0") == "'+CMD|' /C calc'!A0"
    assert sanitize_csv_value("-5.00") == "'-5.00"
    assert sanitize_csv_value("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_value("\tTAB_INJECT") == "'\tTAB_INJECT"
    assert sanitize_csv_value("\rCARRIAGE_INJECT") == "'\rCARRIAGE_INJECT"
    assert sanitize_csv_value("%PERCENT") == "'%PERCENT"

    # Test benign text
    assert sanitize_csv_value("Acme Corp") == "Acme Corp"
    assert sanitize_csv_value("100.50") == "100.50"
    assert sanitize_csv_value("INV-2024-001") == "INV-2024-001"
    assert sanitize_csv_value(None) == ""
    assert sanitize_csv_value("") == ""


def test_processing_summary_and_discrepancy_exporter() -> None:
    doc_id = "DOC-TEST-REP"
    inv_data = InvoiceData(
        invoice_number="INV-001",
        invoice_date=date(2024, 1, 1),
        vendor_name="=FormulaVendor",  # Intentionally triggers sanitization in CSV!
        currency="USD",
        total=Decimal("100.00"),
    )
    ext = InvoiceExtractionRecord(
        document_id=doc_id,
        file_name=f"{doc_id}.pdf",
        data=inv_data,
        raw_fields={
            "invoice_number": "INV-001",
            "vendor_name": "=FormulaVendor",
            "total": "100.00",
        },
        evidence={},
        validation_passed=True,
    )

    disc = Discrepancy(
        discrepancy_id="DISC-01",
        document_id=doc_id,
        rule_id="ARITH_003",
        rule_name="Total Check",
        category=RuleCategory.ARITHMETIC,
        severity=Severity.HIGH,
        outcome=ValidationOutcome.FAIL,
        explanation="+Unsanitized explanation",
    )
    val = ValidationResult(
        document_id=doc_id,
        overall_status=OverallValidationStatus.NEEDS_REVIEW,
        rules_evaluated=19,
        rules_passed=18,
        rules_failed=1,
        discrepancies=[disc],
        recommended_action="Review math",
    )

    rev = ReviewRecord(
        review_id="REV-01",
        document_id=doc_id,
        extraction_reference="test.pdf",
        initial_validation_status=OverallValidationStatus.NEEDS_REVIEW,
        status=ReviewStatus.IN_REVIEW,
        assigned_reviewer="alice",
    )

    # 1. Processing Summary
    summary_dict = ProcessingSummaryExporter.to_dict([ext], [val], [rev])
    assert summary_dict["total_documents"] == 1
    assert summary_dict["total_discrepancies"] == 1
    assert "legally certified audit record" in summary_dict["disclaimer"]

    summary_csv = ProcessingSummaryExporter.to_csv([ext], [val], [rev])
    assert "'=FormulaVendor" in summary_csv  # Sanitized!
    assert "NEEDS_REVIEW" in summary_csv

    # 2. Discrepancy Exporter
    disc_csv = DiscrepancyReportExporter.to_csv([val])
    assert "'+Unsanitized explanation" in disc_csv  # Sanitized!

    disc_json = DiscrepancyReportExporter.to_json([val])
    parsed_json = json.loads(disc_json)
    assert parsed_json["total_discrepancies"] == 1
    assert parsed_json["discrepancies"][0]["rule_id"] == "ARITH_003"


def test_review_and_audit_exporters() -> None:
    doc_id = "DOC-REV-01"
    rev = ReviewRecord(
        review_id="REV-TEST-01",
        document_id=doc_id,
        extraction_reference="test.pdf",
        initial_validation_status=OverallValidationStatus.VALID,
        status=ReviewStatus.APPROVED,
        assigned_reviewer="bob",
        completed_at=datetime.now(UTC),
    )
    rev.decisions.append(
        ReviewDecision(
            decision_type=ReviewDecisionType.APPROVE,
            reviewer="bob",
            reason_code="VERIFIED_CLEAN",
        )
    )
    rev.corrections.append(
        FieldCorrection(
            field_name="total",
            original_value=Decimal("100.00"),
            corrected_value=Decimal("100.00"),
            reason="Confirmed total",
            reviewer="bob",
            status=CorrectionStatus.ACCEPTED,
        )
    )

    # Review outcome export
    rev_csv = ReviewOutcomeExporter.to_csv([rev])
    assert "REV-TEST-01" in rev_csv
    assert "APPROVED" in rev_csv

    rev_json = ReviewOutcomeExporter.to_json([rev])
    assert "REV-TEST-01" in rev_json

    # Correction history export
    corr_csv = CorrectionHistoryExporter.to_csv([rev])
    assert "Confirmed total" in corr_csv

    # Audit history export
    evt = AuditEvent(
        document_id=doc_id,
        review_id=rev.review_id,
        event_type=AuditEventType.DOCUMENT_APPROVED,
        actor="bob",
        new_state="APPROVED",
    )
    audit_csv = AuditHistoryExporter.to_csv([evt])
    assert "DOCUMENT_APPROVED" in audit_csv
    assert "bob" in audit_csv

    audit_json = AuditHistoryExporter.to_json([evt])
    assert "DOCUMENT_APPROVED" in audit_json
