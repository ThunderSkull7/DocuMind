"""Deterministic monetary value and currency parser.

Parses decimal currency strings across Anglo-American (1,234.56) and European
(1.234,56) number conventions without floating-point inaccuracies.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}

KNOWN_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "CAD",
    "AUD",
    "CHF",
    "JPY",
    "NOK",
    "SEK",
    "DKK",
    "NZD",
}


@dataclass
class MoneyParseResult:
    """Outcome of parsing a monetary value."""

    amount: Decimal | None
    currency: str | None
    raw_text: str
    is_valid: bool = True
    is_negative: bool = False
    error: str | None = None


def parse_monetary_value(text: str) -> MoneyParseResult:
    """Parse raw text string into a Decimal monetary amount and currency.

    Handles:
    - USD notation: 1,234.56
    - European notation: 1.234,56 or 1234,56
    - Parenthesized or prefixed negative values: (120.50), -120.50
    - Explicit zero / exempt tokens: EXEMPT / 0.00
    - Embedded currency codes or symbols: EUR 535.50, $120.00, £ 45.00
    """
    raw = text.strip()
    if not raw:
        return MoneyParseResult(
            amount=None,
            currency=None,
            raw_text=text,
            is_valid=False,
            error="Empty monetary string",
        )

    # 1. Detect currency
    currency: str | None = None
    curr_code_match = re.search(
        r"\b(" + "|".join(KNOWN_CURRENCIES) + r")\b",
        raw,
        re.IGNORECASE,
    )
    if curr_code_match:
        currency = curr_code_match.group(1).upper()
    else:
        for sym, code in CURRENCY_SYMBOL_MAP.items():
            if sym in raw:
                currency = code
                break

    # 2. Check for explicit EXEMPT
    if "EXEMPT" in raw.upper():
        return MoneyParseResult(
            amount=None,
            currency=currency,
            raw_text=raw,
            is_valid=True,
            error=None,
        )

    # 3. Detect negative amount
    is_negative = False
    if re.search(r"\(.*\)", raw) or "-" in raw:
        is_negative = True

    # 4. Extract numeric string portion
    # Matches patterns like 1,234.56 or 1.234,56 or 535.50 or 535,50 or 535
    num_match = re.search(r"(\d+(?:[.,\s]\d+)*(?:[.,]\d+)?)", raw)
    if not num_match:
        return MoneyParseResult(
            amount=None,
            currency=currency,
            raw_text=raw,
            is_valid=False,
            error="No numeric amount found",
        )

    num_str = num_match.group(1).strip()

    # Determine decimal point vs thousands separator:
    # If string contains both '.' and ',':
    #   If '.' comes before ',': e.g. 1.234,56 -> European (thousands '.', decimal ',')
    #   If ',' comes before '.': e.g. 1,234.56 -> Anglo (thousands ',', decimal '.')
    # If string contains only ',':
    #   If exactly 2 digits follow ',': e.g. 649,00 or 535,50 -> European decimal
    #   If 3 digits follow ',': e.g. 1,000 -> thousands separator or European decimal?
    #     Standard invoices rarely use thousands separator without decimals.
    # If string contains only '.':
    #   If exactly 2 digits follow '.': e.g. 535.50 -> Anglo decimal
    #   If 3 digits follow '.': e.g. 1.000 -> European thousands

    clean_num: str
    if "." in num_str and "," in num_str:
        if num_str.rfind(",") > num_str.rfind("."):
            # European: 1.234,56 -> 1234.56
            clean_num = num_str.replace(".", "").replace(",", ".")
        else:
            # Anglo: 1,234.56 -> 1234.56
            clean_num = num_str.replace(",", "")
    elif "," in num_str:
        parts = num_str.split(",")
        if len(parts) == 2 and len(parts[1]) in {1, 2}:
            # European decimal: 649,00 -> 649.00
            clean_num = f"{parts[0]}.{parts[1]}"
        elif len(parts) == 2 and len(parts[1]) == 3:
            # 1,000 -> likely 1000.00
            clean_num = "".join(parts)
        else:
            # multiple commas, e.g. 1,000,000
            clean_num = num_str.replace(",", "")
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) == 2 and len(parts[1]) in {1, 2}:
            # Anglo decimal: 535.50
            clean_num = num_str
        elif len(parts) == 2 and len(parts[1]) == 3:
            # European thousands without decimal: 1.000 -> 1000
            clean_num = "".join(parts)
        else:
            # multiple dots, e.g. 1.000.000
            clean_num = num_str.replace(".", "")
    else:
        # plain integer
        clean_num = num_str

    # Remove any whitespace
    clean_num = clean_num.replace(" ", "")

    try:
        dec_val = Decimal(clean_num)
        if is_negative and dec_val > 0:
            dec_val = -dec_val

        # Standardize to 2 decimal places if needed
        dec_val = dec_val.quantize(Decimal("0.01"))

        return MoneyParseResult(
            amount=dec_val,
            currency=currency,
            raw_text=raw,
            is_valid=True,
            is_negative=is_negative,
            error=None,
        )
    except InvalidOperation as err:
        return MoneyParseResult(
            amount=None,
            currency=currency,
            raw_text=raw,
            is_valid=False,
            error=f"Could not convert '{clean_num}' to Decimal: {err}",
        )
