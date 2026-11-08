"""Unit tests for deterministic monetary value parsing and currency normalization."""

from decimal import Decimal

import pytest

from documind.extraction.money_parser import parse_monetary_value


@pytest.mark.unit
def test_parse_usd_style() -> None:
    """Verify standard USD thousands and decimal comma parsing."""
    res = parse_monetary_value("$1,234.56")
    assert res.amount == Decimal("1234.56")
    assert res.currency == "USD"
    assert res.is_valid
    assert not res.is_negative


@pytest.mark.unit
def test_parse_european_style() -> None:
    """Verify European dot-thousands and comma-decimal parsing."""
    res1 = parse_monetary_value("EUR 1.234,56")
    assert res1.amount == Decimal("1234.56")
    assert res1.currency == "EUR"
    assert res1.is_valid

    res2 = parse_monetary_value("649,00")
    assert res2.amount == Decimal("649.00")
    assert res2.is_valid


@pytest.mark.unit
def test_parse_currency_symbols() -> None:
    """Verify mapping of symbols to ISO 4217 currency codes."""
    res_eur = parse_monetary_value("€ 535.50")
    assert res_eur.currency == "EUR"
    assert res_eur.amount == Decimal("535.50")

    res_gbp = parse_monetary_value("£ 98.20")
    assert res_gbp.currency == "GBP"
    assert res_gbp.amount == Decimal("98.20")


@pytest.mark.unit
def test_parse_negative_amounts() -> None:
    """Verify negative monetary values in parenthesized and minus notations."""
    res1 = parse_monetary_value("(120.50)")
    assert res1.amount == Decimal("-120.50")
    assert res1.is_negative

    res2 = parse_monetary_value("-50.00")
    assert res2.amount == Decimal("-50.00")
    assert res2.is_negative


@pytest.mark.unit
def test_parse_exempt_and_zero() -> None:
    """Verify explicit EXEMPT string representation."""
    res = parse_monetary_value("EXEMPT / 0.00")
    assert res.amount is None
    assert res.is_valid


@pytest.mark.unit
def test_parse_empty_and_garbage() -> None:
    """Verify failure on non-monetary inputs."""
    res_empty = parse_monetary_value("")
    assert not res_empty.is_valid

    res_none = parse_monetary_value("NoNumbersHere")
    assert not res_none.is_valid
