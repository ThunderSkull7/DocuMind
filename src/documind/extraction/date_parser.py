"""Deterministic invoice date parser with strict ambiguity detection.

Supports ISO 8601, European (DD/MM/YYYY, DD-MM-YYYY), US (MM/DD/YYYY),
and alphanumeric month formats (DD Mon YYYY). Identifies and flags ambiguous
numeric dates without guessing silently.
"""

import re
from dataclasses import dataclass, field
from datetime import date

MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass
class DateParseResult:
    """Outcome of parsing a candidate date string."""

    parsed_date: date | None
    raw_text: str
    is_ambiguous: bool = False
    candidate_dates: list[date] = field(default_factory=list)
    format_matched: str | None = None
    confidence: float = 1.0
    error: str | None = None


def parse_invoice_date(text: str) -> DateParseResult:
    """Parse raw text snippet into calendar date with ambiguity analysis.

    Args:
        text: Raw date string from document extraction.

    Returns:
        DateParseResult containing parsed date, ambiguity status, and candidates.
    """
    clean_text = text.strip()
    if not clean_text:
        return DateParseResult(
            parsed_date=None,
            raw_text=text,
            is_ambiguous=False,
            confidence=0.0,
            error="Empty date string",
        )

    # 1. ISO 8601: YYYY-MM-DD or YYYY/MM/DD
    iso_match = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", clean_text)
    if iso_match:
        year, month, day = (
            int(iso_match.group(1)),
            int(iso_match.group(2)),
            int(iso_match.group(3)),
        )
        try:
            d = date(year, month, day)
            return DateParseResult(
                parsed_date=d,
                raw_text=clean_text,
                is_ambiguous=False,
                candidate_dates=[d],
                format_matched="YYYY-MM-DD",
                confidence=1.0,
            )
        except ValueError as err:
            return DateParseResult(
                parsed_date=None,
                raw_text=clean_text,
                is_ambiguous=False,
                confidence=0.0,
                error=f"Invalid ISO calendar date: {err}",
            )

    # 2. Alphanumeric Month formats: "DD Mon YYYY", "DD-Mon-YYYY", "Mon DD, YYYY"
    # e.g., "15 Oct 2024", "03-February-2024", "October 15, 2024"
    alpha_match_1 = re.search(
        r"\b(\d{1,2})[\s\-]+([A-Za-z]{3,9})[\s\-]+(\d{4})\b",
        clean_text,
    )
    if alpha_match_1:
        day_val = int(alpha_match_1.group(1))
        month_str = alpha_match_1.group(2).lower()
        year_val = int(alpha_match_1.group(3))
        if month_str in MONTH_NAMES:
            try:
                d = date(year_val, MONTH_NAMES[month_str], day_val)
                return DateParseResult(
                    parsed_date=d,
                    raw_text=clean_text,
                    is_ambiguous=False,
                    candidate_dates=[d],
                    format_matched="DD Mon YYYY",
                    confidence=1.0,
                )
            except ValueError as err:
                return DateParseResult(
                    parsed_date=None,
                    raw_text=clean_text,
                    is_ambiguous=False,
                    confidence=0.0,
                    error=f"Invalid date: {err}",
                )

    alpha_match_2 = re.search(
        r"\b([A-Za-z]{3,9})[\s\-]+(\d{1,2}),?[\s\-]+(\d{4})\b",
        clean_text,
    )
    if alpha_match_2:
        month_str = alpha_match_2.group(1).lower()
        day_val = int(alpha_match_2.group(2))
        year_val = int(alpha_match_2.group(3))
        if month_str in MONTH_NAMES:
            try:
                d = date(year_val, MONTH_NAMES[month_str], day_val)
                return DateParseResult(
                    parsed_date=d,
                    raw_text=clean_text,
                    is_ambiguous=False,
                    candidate_dates=[d],
                    format_matched="Mon DD YYYY",
                    confidence=1.0,
                )
            except ValueError as err:
                return DateParseResult(
                    parsed_date=None,
                    raw_text=clean_text,
                    is_ambiguous=False,
                    confidence=0.0,
                    error=f"Invalid date: {err}",
                )

    # 3. Numeric Dual: DD/MM/YYYY or MM/DD/YYYY or DD-MM-YYYY
    num_match = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", clean_text)
    if num_match:
        part1 = int(num_match.group(1))
        part2 = int(num_match.group(2))
        year = int(num_match.group(3))

        cand_dd_mm: date | None = None
        cand_mm_dd: date | None = None

        # Candidate 1: DD/MM/YYYY
        try:
            cand_dd_mm = date(year, part2, part1)
        except ValueError:
            cand_dd_mm = None

        # Candidate 2: MM/DD/YYYY
        try:
            cand_mm_dd = date(year, part1, part2)
        except ValueError:
            cand_mm_dd = None

        if cand_dd_mm and not cand_mm_dd:
            # Unambiguous DD/MM/YYYY (since part1 > 12)
            return DateParseResult(
                parsed_date=cand_dd_mm,
                raw_text=clean_text,
                is_ambiguous=False,
                candidate_dates=[cand_dd_mm],
                format_matched="DD/MM/YYYY",
                confidence=1.0,
            )

        if cand_mm_dd and not cand_dd_mm:
            # Unambiguous MM/DD/YYYY (since part2 > 12)
            return DateParseResult(
                parsed_date=cand_mm_dd,
                raw_text=clean_text,
                is_ambiguous=False,
                candidate_dates=[cand_mm_dd],
                format_matched="MM/DD/YYYY",
                confidence=1.0,
            )

        if cand_dd_mm and cand_mm_dd:
            if cand_dd_mm == cand_mm_dd:
                # part1 == part2 (e.g., 05/05/2024) -> unambiguous
                return DateParseResult(
                    parsed_date=cand_dd_mm,
                    raw_text=clean_text,
                    is_ambiguous=False,
                    candidate_dates=[cand_dd_mm],
                    format_matched="DD/MM/YYYY",
                    confidence=1.0,
                )

            # Both valid and different -> AMBIGUOUS!
            # We record both candidates. We retain cand_dd_mm as primary interpretation
            # but flag is_ambiguous=True with lower confidence (0.5).
            return DateParseResult(
                parsed_date=cand_dd_mm,
                raw_text=clean_text,
                is_ambiguous=True,
                candidate_dates=[cand_dd_mm, cand_mm_dd],
                format_matched="AMBIGUOUS (DD/MM vs MM/DD)",
                confidence=0.5,
                error="Ambiguous date format: could be DD/MM/YYYY or MM/DD/YYYY",
            )

    return DateParseResult(
        parsed_date=None,
        raw_text=clean_text,
        is_ambiguous=False,
        confidence=0.0,
        error="Date pattern could not be recognized",
    )
