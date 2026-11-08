"""CSV formula-injection sanitization utility for DocuMind reporting.

Protects spreadsheet applications (e.g. Microsoft Excel, LibreOffice Calc) from executing
untrusted formula commands (e.g. '=1+1', '+cmd', '@SUM', '-CMD') embedded in extracted text.
"""

from typing import Any

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "%")


def sanitize_csv_value(val: Any) -> str:
    """Sanitize an arbitrary field value for safe CSV export.

    If the string representation starts with a formula trigger character,
    prefixes a single quote `'` to ensure spreadsheet software treats it
    strictly as plain text.

    Args:
        val: Any Python primitive or object.

    Returns:
        Sanitized string representation.
    """
    if val is None:
        return ""

    text = str(val)
    if not text:
        return ""

    # Check if string begins with any known formula injection trigger
    if text.startswith(FORMULA_PREFIXES):
        return f"'{text}"

    return text
