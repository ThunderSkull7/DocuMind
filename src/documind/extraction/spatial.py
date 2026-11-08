"""Spatial indexing, word clustering, and coordinate merging utilities.

Provides geometric projection, reading line clustering with skew correction,
spatial relation queries (beside, below, above), and bounding-box aggregation across pages.
"""

from dataclasses import dataclass, field

from documind.extraction.models import PageExtractionMethod, SpatialWord
from documind.schemas.invoice import BoundingBox


@dataclass
class SpatialLine:
    """A horizontally aligned sequence of spatial words on a document page."""

    page_number: int
    words: list[SpatialWord] = field(default_factory=list)
    y_center: float = 0.0
    y_center_deskewed: float = 0.0

    @property
    def text(self) -> str:
        """Space-concatenated text of all words in the line."""
        return " ".join(w.text for w in self.words)

    @property
    def bounding_box(self) -> BoundingBox:
        """Merged bounding box covering all constituent words in the line."""
        if not self.words:
            return BoundingBox(page=self.page_number, x0=0.0, y0=0.0, x1=0.0, y1=0.0)
        x0 = min(w.bounding_box.x0 for w in self.words)
        y0 = min(w.bounding_box.y0 for w in self.words)
        x1 = max(w.bounding_box.x1 for w in self.words)
        y1 = max(w.bounding_box.y1 for w in self.words)
        return BoundingBox(page=self.page_number, x0=x0, y0=y0, x1=x1, y1=y1)


def merge_bounding_boxes(words: list[SpatialWord], page_number: int) -> BoundingBox | None:
    """Compute the minimum bounding rectangle enclosing all provided words."""
    if not words:
        return None
    x0 = min(w.bounding_box.x0 for w in words)
    y0 = min(w.bounding_box.y0 for w in words)
    x1 = max(w.bounding_box.x1 for w in words)
    y1 = max(w.bounding_box.y1 for w in words)
    return BoundingBox(page=page_number, x0=x0, y0=y0, x1=x1, y1=y1)


def get_words_source_method(words: list[SpatialWord]) -> str:
    """Determine whether words originated from OCR or native extraction."""
    if not words:
        return "native_text"
    if any(w.extraction_method == PageExtractionMethod.OCR for w in words):
        return "ocr"
    return "native_text"


def get_words_ocr_confidence(words: list[SpatialWord]) -> float | None:
    """Compute average OCR confidence across words if OCR was used."""
    ocr_words = [w for w in words if w.confidence is not None]
    if not ocr_words:
        return None
    return round(sum(w.confidence for w in ocr_words) / len(ocr_words), 4)


def estimate_page_skew_slope(words: list[SpatialWord]) -> float:
    """Estimate the rotational skew slope (dy/dx = tan(theta)) across words on the page."""
    if len(words) < 2:
        return 0.0

    slopes: list[float] = []
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i + 1]
        dx = w2.bounding_box.x0 - w1.bounding_box.x0
        dy = (
            (w2.bounding_box.y0 + w2.bounding_box.y1) - (w1.bounding_box.y0 + w1.bounding_box.y1)
        ) / 2.0
        # If words are on roughly the same printed line (dx between 20 and 150 pt, dy < 15 pt)
        if 20.0 <= dx <= 150.0 and abs(dy) <= 15.0:
            slopes.append(dy / dx)

    if not slopes:
        return 0.0

    slopes.sort()
    return slopes[len(slopes) // 2]


def cluster_words_into_lines(
    words: list[SpatialWord],
    y_tolerance: float = 6.0,
) -> list[SpatialLine]:
    """Cluster words into reading lines based on vertical proximity with skew compensation.

    Estimates page-level skew and projects coordinates onto deskewed baselines,
    preventing rotated or skewed OCR lines from splitting across multiple rows.
    """
    if not words:
        return []

    page_num = words[0].page_number
    skew_slope = estimate_page_skew_slope(words)

    # Sort words by deskewed vertical midpoint: y' = y - (x * slope)
    sorted_words = sorted(
        words,
        key=lambda w: (
            ((w.bounding_box.y0 + w.bounding_box.y1) / 2.0)
            - (((w.bounding_box.x0 + w.bounding_box.x1) / 2.0) * skew_slope),
            w.bounding_box.x0,
        ),
    )

    lines: list[SpatialLine] = []

    for word in sorted_words:
        w_mid = (word.bounding_box.y0 + word.bounding_box.y1) / 2.0
        w_x = (word.bounding_box.x0 + word.bounding_box.x1) / 2.0
        w_mid_deskewed = w_mid - (w_x * skew_slope)

        matched_line: SpatialLine | None = None
        best_diff = y_tolerance

        for line in lines:
            diff = abs(line.y_center_deskewed - w_mid_deskewed)
            if diff < best_diff:
                best_diff = diff
                matched_line = line

        if matched_line:
            matched_line.words.append(word)
            # Recompute running centers
            matched_line.y_center = sum(
                (w.bounding_box.y0 + w.bounding_box.y1) / 2.0 for w in matched_line.words
            ) / len(matched_line.words)
            matched_line.y_center_deskewed = sum(
                ((w.bounding_box.y0 + w.bounding_box.y1) / 2.0)
                - (((w.bounding_box.x0 + w.bounding_box.x1) / 2.0) * skew_slope)
                for w in matched_line.words
            ) / len(matched_line.words)
        else:
            sl = SpatialLine(
                page_number=page_num,
                words=[word],
                y_center=w_mid,
                y_center_deskewed=w_mid_deskewed,
            )
            lines.append(sl)

    # Sort lines vertically from top to bottom
    lines.sort(key=lambda line: line.y_center)

    # Sort words within each line left to right by x0
    for line in lines:
        line.words.sort(key=lambda w: w.bounding_box.x0)

    return lines
