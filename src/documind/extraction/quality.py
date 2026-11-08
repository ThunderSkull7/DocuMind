"""Page text quality assessment for hybrid extraction routing."""

from documind.config import Settings, get_settings
from documind.extraction.models import ExtractionQuality


def assess_page_quality(
    raw_text: str,
    page_width: float,
    page_height: float,
    settings: Settings | None = None,
) -> ExtractionQuality:
    """Evaluate textual quality metrics to decide if native extraction is sufficient.

    Args:
        raw_text: Raw text extracted from page.
        page_width: Width of page in PDF points.
        page_height: Height of page in PDF points.
        settings: Application settings with routing thresholds.

    Returns:
        ExtractionQuality container with computed metrics and sufficiency verdict.
    """
    cfg = settings or get_settings()
    cleaned = raw_text.strip()
    char_count = len(cleaned)
    words = cleaned.split()
    word_count = len(words)

    # Compute alphanumeric ratio
    alnum_count = sum(1 for c in cleaned if c.isalnum())
    alpha_ratio = (alnum_count / char_count) if char_count > 0 else 0.0

    # Compute text density per 1,000 square PDF points
    page_area = page_width * page_height
    text_density = (char_count * 1000.0 / page_area) if page_area > 0 else 0.0

    # Detect Unicode replacement characters (sign of font encoding corruption)
    replacement_count = raw_text.count("\ufffd")

    # Evaluate sufficiency against configured thresholds
    is_sufficient = (
        char_count >= cfg.routing_min_char_count
        and alpha_ratio >= cfg.routing_min_alpha_ratio
        and word_count >= cfg.routing_min_word_count
        and replacement_count < 5
    )

    signals = {
        "raw_character_count": char_count,
        "word_count": word_count,
        "alphanumeric_characters": alnum_count,
        "alphanumeric_ratio": round(alpha_ratio, 4),
        "text_density_per_1k_pt": round(text_density, 4),
        "replacement_characters": replacement_count,
        "threshold_min_char_count": cfg.routing_min_char_count,
        "threshold_min_alpha_ratio": cfg.routing_min_alpha_ratio,
        "threshold_min_word_count": cfg.routing_min_word_count,
    }

    return ExtractionQuality(
        character_count=char_count,
        word_count=word_count,
        alphanumeric_ratio=round(alpha_ratio, 4),
        text_density=round(text_density, 4),
        replacement_char_count=replacement_count,
        is_sufficient_for_native=is_sufficient,
        signals=signals,
    )
