"""Unit tests for deterministic business rules and logical validation."""

from datetime import date
from decimal import Decimal

import pytest

from documind.schemas.invoice import (
    EvidenceStatus,
    ExtractionMethod,
    FieldEvidence,
    InvoiceExtractionRecord,
)
from documind.validation.business_rules import BusinessRulesValidator
from documind.validation.models import Severity, ValidationOutcome


@pytest.fixture
def validator() -> BusinessRulesValidator:
    return BusinessRulesValidator(reference_date=date(2024, 11, 8))


@pytest.mark.unit
def test_mandatory_fields_missing(validator: BusinessRulesValidator) -> None:
    """Verify that omitting required fields generates CRITICAL FAIL discrepancies."""
    record = InvoiceExtractionRecord(
        document_id="TEST-BIZ-001",
        file_name="missing_inv_num.pdf",
        raw_fields={
            "invoice_number": None,
            "invoice_date": date(2024, 5, 1),
            "vendor_name": "Acme Corp",
            "total": Decimal("100.00"),
            "currency": "USD",
        },
        evidence={
            "invoice_number": FieldEvidence(
                field_name="invoice_number",
                raw_text="[NOT SPECIFIED]",
                confidence=0.0,
                method=ExtractionMethod.RULE_BASED,
                status=EvidenceStatus.MISSING,
            )
        },
    )

    discs = validator.validate(record)
    assert any(
        d.rule_id == "BIZ_001"
        and d.severity == Severity.CRITICAL
        and d.affected_fields == ["invoice_number"]
        for d in discs
    )


@pytest.mark.unit
def test_temporal_ordering_violation(validator: BusinessRulesValidator) -> None:
    """Verify that invoice_date > due_date generates a HIGH severity FAIL."""
    record = InvoiceExtractionRecord(
        document_id="TEST-BIZ-002",
        file_name="inconsistent_dates.pdf",
        raw_fields={
            "invoice_number": "INV-100",
            "invoice_date": date(2024, 11, 20),
            "due_date": date(2024, 11, 5),  # Due date is earlier than invoice date!
            "vendor_name": "Acme Corp",
            "total": Decimal("100.00"),
            "currency": "USD",
        },
    )

    discs = validator.validate(record)
    assert any(
        d.rule_id == "BIZ_002"
        and d.outcome == ValidationOutcome.FAIL
        and d.severity == Severity.HIGH
        for d in discs
    )


@pytest.mark.unit
def test_ambiguous_field_warning(validator: BusinessRulesValidator) -> None:
    """Verify that EvidenceStatus.AMBIGUOUS triggers a MEDIUM severity WARNING."""
    record = InvoiceExtractionRecord(
        document_id="TEST-BIZ-003",
        file_name="ambiguous_date.pdf",
        raw_fields={
            "invoice_number": "INV-101",
            "invoice_date": date(2024, 4, 3),
            "vendor_name": "Acme Corp",
            "total": Decimal("100.00"),
            "currency": "USD",
        },
        evidence={
            "invoice_date": FieldEvidence(
                field_name="invoice_date",
                raw_text="03/04/2024",
                confidence=0.5,
                method=ExtractionMethod.PATTERN,
                status=EvidenceStatus.AMBIGUOUS,
                candidates=["2024-03-04", "2024-04-03"],
            )
        },
    )

    discs = validator.validate(record)
    assert any(
        d.rule_id == "BIZ_004"
        and d.outcome == ValidationOutcome.WARNING
        and d.affected_fields == ["invoice_date"]
        for d in discs
    )


@pytest.mark.unit
def test_stale_invoice_warning(validator: BusinessRulesValidator) -> None:
    """Verify invoices older than 10 years trigger LOW severity WARNING."""
    record = InvoiceExtractionRecord(
        document_id="TEST-BIZ-004",
        file_name="stale_invoice.pdf",
        raw_fields={
            "invoice_number": "INV-102",
            "invoice_date": date(2010, 1, 1),  # Over 10 years old
            "vendor_name": "Acme Corp",
            "total": Decimal("100.00"),
            "currency": "USD",
        },
    )

    discs = validator.validate(record)
    assert any(
        d.rule_id == "BIZ_003"
        and d.outcome == ValidationOutcome.WARNING
        and d.severity == Severity.LOW
        for d in discs
    )


@pytest.mark.unit
def test_confusable_glyph_warning(validator: BusinessRulesValidator) -> None:
    """Verify identifiers mixing 0/O or 1/I/l trigger glyph ambiguity warning."""
    record = InvoiceExtractionRecord(
        document_id="TEST-BIZ-005",
        file_name="glyph_confusable.pdf",
        raw_fields={
            "invoice_number": "INV-0O1I1lB8",
            "invoice_date": date(2024, 5, 1),
            "vendor_name": "Acme Corp",
            "total": Decimal("100.00"),
            "currency": "USD",
        },
    )

    discs = validator.validate(record)
    assert any(
        d.rule_id == "BIZ_008"
        and d.outcome == ValidationOutcome.WARNING
        and d.severity == Severity.INFO
        for d in discs
    )
