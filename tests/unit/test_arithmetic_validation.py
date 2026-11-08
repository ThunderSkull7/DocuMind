"""Unit tests for deterministic Decimal arithmetic validation."""

from decimal import Decimal

import pytest

from documind.schemas.invoice import InvoiceExtractionRecord, InvoiceLineItem
from documind.validation.arithmetic import ArithmeticValidator
from documind.validation.models import Severity, ValidationOutcome


@pytest.fixture
def validator() -> ArithmeticValidator:
    return ArithmeticValidator(rounding_tolerance=Decimal("0.02"))


@pytest.mark.unit
def test_arithmetic_clean_match(validator: ArithmeticValidator) -> None:
    """Verify clean invoice passes all arithmetic checks without discrepancies."""
    items = [
        InvoiceLineItem(
            description="Item 1",
            quantity=Decimal("2"),
            unit_price=Decimal("50.00"),
            total=Decimal("100.00"),
        ),
        InvoiceLineItem(
            description="Item 2",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            total=Decimal("100.00"),
        ),
    ]
    record = InvoiceExtractionRecord(
        document_id="TEST-001",
        file_name="test.pdf",
        raw_fields={
            "subtotal": Decimal("200.00"),
            "tax": Decimal("20.00"),
            "total": Decimal("220.00"),
            "line_items": items,
        },
    )

    discs = validator.validate(record)
    assert len(discs) == 0


@pytest.mark.unit
def test_arithmetic_total_mismatch(validator: ArithmeticValidator) -> None:
    """Verify that subtotal + tax != total is flagged with HIGH severity."""
    record = InvoiceExtractionRecord(
        document_id="TEST-002",
        file_name="test.pdf",
        raw_fields={
            "subtotal": Decimal("100.00"),
            "tax": Decimal("10.00"),
            "total": Decimal("160.00"),  # Expected: 110.00, Diff: +50.00
            "line_items": [],
        },
    )

    discs = validator.validate(record)
    assert len(discs) == 1
    d = discs[0]
    assert d.rule_id == "ARITH_003"
    assert d.outcome == ValidationOutcome.FAIL
    assert d.severity == Severity.HIGH
    assert d.expected_value == Decimal("110.00")
    assert d.actual_value == Decimal("160.00")
    assert d.difference == Decimal("50.00")


@pytest.mark.unit
def test_line_item_math_mismatch(validator: ArithmeticValidator) -> None:
    """Verify that quantity x unit price != line item total is flagged."""
    item = InvoiceLineItem(
        description="Consulting",
        quantity=Decimal("4"),
        unit_price=Decimal("50.00"),
        total=Decimal("250.00"),  # Expected: 200.00
    )
    record = InvoiceExtractionRecord(
        document_id="TEST-003",
        file_name="test.pdf",
        raw_fields={
            "subtotal": Decimal("250.00"),
            "tax": Decimal("25.00"),
            "total": Decimal("275.00"),
            "line_items": [item],
        },
    )

    discs = validator.validate(record)
    assert any(d.rule_id == "ARITH_001" and d.outcome == ValidationOutcome.FAIL for d in discs)


@pytest.mark.unit
def test_line_items_sum_vs_subtotal_mismatch(validator: ArithmeticValidator) -> None:
    """Verify that sum of line items != stated subtotal is flagged."""
    item1 = InvoiceLineItem(
        description="Widget A",
        quantity=Decimal("1"),
        unit_price=Decimal("50.00"),
        total=Decimal("50.00"),
    )
    item2 = InvoiceLineItem(
        description="Widget B",
        quantity=Decimal("1"),
        unit_price=Decimal("70.00"),
        total=Decimal("70.00"),
    )
    record = InvoiceExtractionRecord(
        document_id="TEST-004",
        file_name="test.pdf",
        raw_fields={
            "subtotal": Decimal("200.00"),  # Items sum = 120.00
            "tax": Decimal("20.00"),
            "total": Decimal("220.00"),
            "line_items": [item1, item2],
        },
    )

    discs = validator.validate(record)
    assert any(d.rule_id == "ARITH_002" and d.outcome == ValidationOutcome.FAIL for d in discs)


@pytest.mark.unit
def test_subtotal_exceeds_total(validator: ArithmeticValidator) -> None:
    """Verify that subtotal > total triggers ARITH_004."""
    record = InvoiceExtractionRecord(
        document_id="TEST-005",
        file_name="test.pdf",
        raw_fields={
            "subtotal": Decimal("300.00"),
            "tax": Decimal("20.00"),
            "total": Decimal("250.00"),
            "line_items": [],
        },
    )

    discs = validator.validate(record)
    assert any(d.rule_id == "ARITH_004" and d.outcome == ValidationOutcome.FAIL for d in discs)


@pytest.mark.unit
def test_balance_due_calculation(validator: ArithmeticValidator) -> None:
    """Verify balance due vs total - amount paid calculation."""
    record = InvoiceExtractionRecord(
        document_id="TEST-006",
        file_name="test.pdf",
        raw_fields={
            "total": Decimal("500.00"),
            "amount_paid": Decimal("200.00"),
            "balance_due": Decimal("250.00"),  # Expected: 300.00
            "line_items": [],
        },
    )

    discs = validator.validate(record)
    assert any(d.rule_id == "ARITH_005" and d.outcome == ValidationOutcome.FAIL for d in discs)


@pytest.mark.unit
def test_missing_components_return_indeterminate(validator: ArithmeticValidator) -> None:
    """Verify missing values return INDETERMINATE rather than false failures."""
    item = InvoiceLineItem(
        description="Hourly Task",
        quantity=None,
        unit_price=Decimal("50.00"),
        total=Decimal("150.00"),
    )
    record = InvoiceExtractionRecord(
        document_id="TEST-007",
        file_name="test.pdf",
        raw_fields={
            "total": Decimal("150.00"),
            "line_items": [item],
        },
    )

    discs = validator.validate(record)
    assert any(
        d.rule_id == "ARITH_001" and d.outcome == ValidationOutcome.INDETERMINATE for d in discs
    )
