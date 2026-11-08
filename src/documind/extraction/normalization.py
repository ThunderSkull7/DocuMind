"""Deterministic text normalization for DocuMind extraction pipeline.

Applies safe whitespace and control-character sanitization while strictly
preserving decimal separators, currency symbols, invoice identifiers, and line boundaries.
"""

import re

# Control characters to strip: ASCII 0-8, 11-12, 14-31, 127
# Explicitly preserves \t (9) and \n (10)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_text(text: str) -> str:
    """Normalize extracted text deterministically without altering domain values.

    Operations performed:
    1. Unify line endings (CRLF, CR -> LF).
    2. Strip non-printable ASCII control characters.
    3. Normalize horizontal whitespace (tabs and multiple spaces -> single space).
    4. Collapse runs of 3+ consecutive newlines to 2 newlines (preserving paragraphs).
    5. Strip trailing whitespace from individual lines.

    Preserves:
    - Decimal points and commas in numbers (e.g. '1,450.50', '1.450,50').
    - Currency symbols ($, EUR, GBP, Yen, etc.).
    - Alphanumeric codes, hyphenated identifiers, and slash dates.

    Args:
        text: Raw extracted text string.

    Returns:
        Cleaned, normalized text string.
    """
    if not text:
        return ""

    # 1. Unify line endings
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip harmful control characters
    normalized = CONTROL_CHAR_PATTERN.sub("", normalized)

    # 3. Process line by line to preserve line structure
    lines = normalized.split("\n")
    cleaned_lines: list[str] = []

    for line in lines:
        # Collapse multiple horizontal whitespace characters (spaces, tabs) into a single space
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(cleaned_line)

    normalized = "\n".join(cleaned_lines)

    # 4. Collapse runs of 3 or more newlines to at most 2 newlines
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    return normalized.strip()
