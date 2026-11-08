"""Property-based and mathematical invariant unit tests for DocuMind.

Verifies:
1. Fixed-point decimal arithmetic invariants (zero float precision drift).
2. Spatial coordinate projection and containment under arbitrary DPI scaling.
3. Date parsing stability and ambiguity detection invariants.
4. Formula injection sanitization invariants (CWE-1236).
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from documind.extraction.date_parser import parse_invoice_date
from documind.extraction.money_parser import parse_monetary_value
from documind.reporting.csv_sanitizer import sanitize_csv_value
from documind.schemas.invoice import BoundingBox


@pytest.mark.unit
def test_fixed_point_decimal_summation_invariance() -> None:
    """Verify that multi-item decimal calculations never accumulate IEEE 754 floating-point drift."""
    # Classical float drift example: 0.1 + 0.2 != 0.3 in IEEE 754
    assert (0.1 + 0.2) != 0.3  # Demonstrating float failure: 0.30000000000000004 != 0.3

    # Decimal fixed-point summation
    d_items = [Decimal("0.10"), Decimal("0.20")]
    assert sum(d_items) == Decimal("0.30")

    # Varied item rows with fractional tax
    quantities = [Decimal("1"), Decimal("3"), Decimal("7"), Decimal("12")]
    prices = [Decimal("19.99"), Decimal("4.50"), Decimal("0.85"), Decimal("102.40")]

    subtotal = Decimal("0.00")
    for q, p in zip(quantities, prices, strict=True):
        line_total = (q * p).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total

    assert subtotal == Decimal("1268.24")

    # 10% tax
    tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = subtotal + tax
    assert tax == Decimal("126.82")
    assert total == Decimal("1395.06")


@pytest.mark.unit
def test_money_parser_currency_and_separators_invariance() -> None:
    """Verify that European and US number formats parse to identical Decimal values."""
    us_val = parse_monetary_value("$1,234.56").amount
    eu_val = parse_monetary_value("1.234,56 €").amount
    clean_val = parse_monetary_value("1234.56").amount

    assert us_val == Decimal("1234.56")
    assert eu_val == Decimal("1234.56")
    assert clean_val == Decimal("1234.56")
    assert us_val == eu_val == clean_val


@pytest.mark.unit
@pytest.mark.parametrize("dpi", [72, 100, 150, 200, 300])
def test_spatial_coordinate_projection_containment_invariance(dpi: int) -> None:
    """Verify that projecting PDF points to pixel space preserves bounding box containment at any DPI."""
    page_w_pt = 595.0
    page_h_pt = 842.0

    # Scale factor from 72 pt/inch
    scale = dpi / 72.0
    rendered_w = int(page_w_pt * scale)
    rendered_h = int(page_h_pt * scale)

    # Box inside page
    box = BoundingBox(x0=50.0, y0=100.0, x1=250.0, y1=140.0, page=1)

    # Projected pixel coordinates
    px0 = box.x0 * (rendered_w / page_w_pt)
    py0 = box.y0 * (rendered_h / page_h_pt)
    px1 = box.x1 * (rendered_w / page_w_pt)
    py1 = box.y1 * (rendered_h / page_h_pt)

    # Invariants
    assert 0.0 <= px0 < px1 <= rendered_w
    assert 0.0 <= py0 < py1 <= rendered_h
    # Aspect ratio preservation
    pt_aspect = (box.x1 - box.x0) / (box.y1 - box.y0)
    px_aspect = (px1 - px0) / (py1 - py0)
    assert abs(pt_aspect - px_aspect) < 1e-2


@pytest.mark.unit
def test_date_parser_ambiguity_invariant() -> None:
    """Verify that slash dates with day <= 12 and month <= 12 are flagged as AMBIGUOUS."""
    # 03/04/2024 could be March 4 or April 3
    res1 = parse_invoice_date("03/04/2024")
    assert res1.is_ambiguous is True
    assert len(res1.candidate_dates) == 2

    # 25/04/2024 is strictly day 25, month 04 (unambiguous)
    res2 = parse_invoice_date("25/04/2024")
    assert res2.is_ambiguous is False
    assert res2.parsed_date is not None
    assert res2.parsed_date.isoformat() == "2024-04-25"


@pytest.mark.unit
@pytest.mark.parametrize(
    "untrusted_input,expected_sanitized",
    [
        ("=1+1", "'=1+1"),
        ("-SUM(A1:A10)", "'-SUM(A1:A10)"),
        ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
        ("@evil_macro()", "'@evil_macro()"),
        ("%SystemRoot%", "'%SystemRoot%"),
        ("\tTabIndented", "'\tTabIndented"),
        ("Safe Vendor Inc.", "Safe Vendor Inc."),
        ("INV-2024-001", "INV-2024-001"),
        (1234.56, "1234.56"),
        (None, ""),
    ],
)
def test_csv_sanitizer_invariants(untrusted_input: object, expected_sanitized: str) -> None:
    """Verify CWE-1236 formula-injection sanitization across safe and malicious inputs."""
    assert sanitize_csv_value(untrusted_input) == expected_sanitized
