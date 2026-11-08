"""Unit tests for deterministic invoice date parser and ambiguity detection."""

from datetime import date

import pytest

from documind.extraction.date_parser import parse_invoice_date


@pytest.mark.unit
def test_parse_iso_date() -> None:
    """Verify unambiguous parsing of ISO 8601 dates."""
    res = parse_invoice_date("2024-02-03")
    assert res.parsed_date == date(2024, 2, 3)
    assert not res.is_ambiguous
    assert res.format_matched == "YYYY-MM-DD"
    assert res.confidence == 1.0


@pytest.mark.unit
def test_parse_alphanumeric_month() -> None:
    """Verify parsing of dates with named months."""
    res1 = parse_invoice_date("15 Oct 2024")
    assert res1.parsed_date == date(2024, 10, 15)
    assert not res1.is_ambiguous

    res2 = parse_invoice_date("03-February-2024")
    assert res2.parsed_date == date(2024, 2, 3)
    assert not res2.is_ambiguous

    res3 = parse_invoice_date("October 15, 2024")
    assert res3.parsed_date == date(2024, 10, 15)
    assert not res3.is_ambiguous


@pytest.mark.unit
def test_unambiguous_dual_numeric_dates() -> None:
    """Verify dates where one component is > 12 are resolved unambiguously."""
    # 25/01/2024 -> part1=25 (>12) -> must be DD/MM/YYYY
    res_dd = parse_invoice_date("25/01/2024")
    assert res_dd.parsed_date == date(2024, 1, 25)
    assert not res_dd.is_ambiguous
    assert res_dd.format_matched == "DD/MM/YYYY"

    # 01/25/2024 -> part2=25 (>12) -> must be MM/DD/YYYY
    res_mm = parse_invoice_date("01/25/2024")
    assert res_mm.parsed_date == date(2024, 1, 25)
    assert not res_mm.is_ambiguous
    assert res_mm.format_matched == "MM/DD/YYYY"


@pytest.mark.unit
def test_ambiguous_numeric_date() -> None:
    """Verify that dates like 03/04/2024 are marked ambiguous and retain candidates."""
    res = parse_invoice_date("03/04/2024")
    assert res.is_ambiguous
    assert res.confidence == 0.5
    assert len(res.candidate_dates) == 2
    assert date(2024, 4, 3) in res.candidate_dates
    assert date(2024, 3, 4) in res.candidate_dates
    assert "Ambiguous" in (res.error or "")


@pytest.mark.unit
def test_identical_day_month_numeric_date() -> None:
    """Verify dates where day == month (e.g., 05/05/2024) are not marked ambiguous."""
    res = parse_invoice_date("05/05/2024")
    assert res.parsed_date == date(2024, 5, 5)
    assert not res.is_ambiguous


@pytest.mark.unit
def test_invalid_and_empty_dates() -> None:
    """Verify graceful failure on empty or invalid calendar dates."""
    res_empty = parse_invoice_date("")
    assert res_empty.parsed_date is None
    assert res_empty.confidence == 0.0

    res_invalid = parse_invoice_date("2024-02-31")
    assert res_invalid.parsed_date is None
    assert "Invalid" in (res_invalid.error or "")

    res_garbage = parse_invoice_date("NotADateString")
    assert res_garbage.parsed_date is None
