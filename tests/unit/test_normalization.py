"""Unit tests for deterministic text normalization."""

import pytest

from documind.extraction.normalization import normalize_text


@pytest.mark.unit
def test_line_ending_unification() -> None:
    """Verify CRLF and CR line endings are unified to LF."""
    raw = "Line 1\r\nLine 2\rLine 3\nLine 4"
    normalized = normalize_text(raw)
    assert "\r" not in normalized
    assert normalized == "Line 1\nLine 2\nLine 3\nLine 4"


@pytest.mark.unit
def test_control_character_removal() -> None:
    """Verify non-printable control characters are removed while newlines and tabs are handled."""
    raw = "Invoice \x00Number:\x07 INV-\x1b2024"
    normalized = normalize_text(raw)
    assert normalized == "Invoice Number: INV-2024"


@pytest.mark.unit
def test_horizontal_whitespace_collapsing() -> None:
    """Verify consecutive horizontal spaces and tabs are collapsed to a single space."""
    raw = "Total:     \t   $1,250.00"
    normalized = normalize_text(raw)
    assert normalized == "Total: $1,250.00"


@pytest.mark.unit
def test_excessive_newlines_collapsing() -> None:
    """Verify 3+ consecutive newlines are collapsed to at most 2 newlines."""
    raw = "Header\n\n\n\n\nBody paragraph"
    normalized = normalize_text(raw)
    assert normalized == "Header\n\nBody paragraph"


@pytest.mark.unit
def test_decimal_and_currency_preservation() -> None:
    """Verify decimal numbers, commas, and currency symbols are completely preserved."""
    test_cases = [
        "Subtotal: $1,250.50",
        "VAT: € 240,75",
        "Total: £9,999.99",
        "Total: ¥150,000",
        "Balance: 1.450,25 €",
    ]
    for case in test_cases:
        assert normalize_text(case) == case


@pytest.mark.unit
def test_invoice_identifier_preservation() -> None:
    """Verify complex and unusual invoice identifiers are not corrupted."""
    identifiers = [
        "INV-2024-00941",
        "INV-0O1I1lB8",
        "TAX/2024/OCT/001",
        "PO#992-8192-A",
    ]
    for ident in identifiers:
        assert normalize_text(ident) == ident


@pytest.mark.unit
def test_raw_text_immutability() -> None:
    """Verify that the input string is not modified in-place."""
    original = "  Original  Text   \r\n"
    _ = normalize_text(original)
    assert original == "  Original  Text   \r\n"
