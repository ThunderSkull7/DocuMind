"""Evidence mapping and provenance validation subsystem for DocuMind.

Ensures every extracted field value is grounded with traceable evidence,
including coordinate bounding boxes, page indices, source extraction methods,
OCR confidences, and honest uncertainty/ambiguity flags.
"""

from typing import Any

from documind.extraction.models import SpatialWord
from documind.extraction.spatial import (
    get_words_ocr_confidence,
    get_words_source_method,
    merge_bounding_boxes,
)
from documind.schemas.invoice import (
    BoundingBox,
    EvidenceStatus,
    ExtractionMethod,
    FieldEvidence,
)


class EvidenceMapper:
    """Constructs and validates grounding evidence for extracted invoice fields."""

    @staticmethod
    def create_evidence(
        field_name: str,
        extracted_value: Any,
        raw_text: str,
        page_number: int | None,
        bounding_box: BoundingBox | None,
        method: ExtractionMethod = ExtractionMethod.RULE_BASED,
        source_method: str | None = None,
        ocr_confidence: float | None = None,
        status: EvidenceStatus = EvidenceStatus.EXTRACTED,
        candidates: list[Any] | None = None,
        confidence: float = 1.0,
        warnings: list[str] | None = None,
    ) -> FieldEvidence:
        """Create a standardized FieldEvidence instance with provenance."""
        return FieldEvidence(
            field_name=field_name,
            extracted_value=extracted_value,
            raw_text=raw_text,
            page_number=page_number,
            bounding_box=bounding_box,
            method=method,
            source_method=source_method,
            ocr_confidence=ocr_confidence,
            status=status,
            candidates=candidates or [],
            confidence=confidence,
            warnings=warnings or [],
        )

    @staticmethod
    def create_from_words(
        field_name: str,
        extracted_value: Any,
        words: list[SpatialWord],
        page_number: int,
        raw_text: str | None = None,
        method: ExtractionMethod = ExtractionMethod.SPATIAL,
        status: EvidenceStatus = EvidenceStatus.EXTRACTED,
        candidates: list[Any] | None = None,
        confidence: float = 1.0,
        warnings: list[str] | None = None,
    ) -> FieldEvidence:
        """Create FieldEvidence synthesized from constituent spatial words."""
        bbox = merge_bounding_boxes(words, page_number) if words else None
        source_method = get_words_source_method(words) if words else "native_text"
        ocr_conf = get_words_ocr_confidence(words) if words else None
        text_str = raw_text if raw_text is not None else (" ".join(w.text for w in words))

        return FieldEvidence(
            field_name=field_name,
            extracted_value=extracted_value,
            raw_text=text_str,
            page_number=page_number,
            bounding_box=bbox,
            method=method,
            source_method=source_method,
            ocr_confidence=ocr_conf,
            status=status,
            candidates=candidates or [],
            confidence=confidence,
            warnings=warnings or [],
        )

    @staticmethod
    def create_missing_evidence(
        field_name: str,
        reason: str = "Field omitted from document",
        raw_text: str = "[NOT SPECIFIED]",
    ) -> FieldEvidence:
        """Create a FieldEvidence entry explicitly denoting a missing required or optional field."""
        return FieldEvidence(
            field_name=field_name,
            extracted_value=None,
            raw_text=raw_text,
            page_number=None,
            bounding_box=None,
            method=ExtractionMethod.RULE_BASED,
            source_method=None,
            ocr_confidence=None,
            status=EvidenceStatus.MISSING,
            candidates=[],
            confidence=0.0,
            warnings=[reason],
        )

    @staticmethod
    def validate_bounding_box(
        bbox: BoundingBox | None,
        page_width: float,
        page_height: float,
    ) -> tuple[bool, str | None]:
        """Verify that bounding box coordinates fall within physical page boundaries."""
        if bbox is None:
            return True, None

        if bbox.x0 < -0.1 or bbox.y0 < -0.1:
            return False, f"Negative coordinate in bounding box: ({bbox.x0}, {bbox.y0})"
        if bbox.x1 > page_width + 0.1 or bbox.y1 > page_height + 0.1:
            return (
                False,
                f"Bounding box exceeds page dimensions ({page_width}x{page_height}): ({bbox.x1}, {bbox.y1})",
            )
        if bbox.x0 > bbox.x1 or bbox.y0 > bbox.y1:
            return (
                False,
                f"Inverted bounding box dimensions: ({bbox.x0}, {bbox.y0}, {bbox.x1}, {bbox.y1})",
            )

        return True, None
