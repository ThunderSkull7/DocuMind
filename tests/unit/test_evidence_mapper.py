"""Unit tests for evidence mapper and coordinate bounding box validation."""

import pytest

from documind.extraction.evidence_mapper import EvidenceMapper
from documind.extraction.models import PageExtractionMethod, SpatialWord
from documind.schemas.invoice import BoundingBox, EvidenceStatus, ExtractionMethod


@pytest.mark.unit
def test_create_evidence_from_scratch() -> None:
    """Verify manual evidence instantiation and attribute tracking."""
    bbox = BoundingBox(page=1, x0=50.0, y0=100.0, x1=200.0, y1=120.0)
    ev = EvidenceMapper.create_evidence(
        field_name="total",
        extracted_value="589.05",
        raw_text="EUR 589.05",
        page_number=1,
        bounding_box=bbox,
        method=ExtractionMethod.RULE_BASED,
        source_method="native_text",
        status=EvidenceStatus.EXTRACTED,
    )
    assert ev.field_name == "total"
    assert ev.extracted_value == "589.05"
    assert ev.bounding_box.x0 == 50.0
    assert ev.status == EvidenceStatus.EXTRACTED


@pytest.mark.unit
def test_create_from_words() -> None:
    """Verify merging bounding boxes and OCR confidences from words."""
    w1 = SpatialWord(
        text="INV-2024",
        page_number=1,
        bounding_box=BoundingBox(page=1, x0=10.0, y0=20.0, x1=50.0, y1=30.0),
        reading_order_index=0,
        extraction_method=PageExtractionMethod.OCR,
        confidence=0.95,
    )
    w2 = SpatialWord(
        text="001",
        page_number=1,
        bounding_box=BoundingBox(page=1, x0=52.0, y0=20.0, x1=70.0, y1=30.0),
        reading_order_index=1,
        extraction_method=PageExtractionMethod.OCR,
        confidence=0.91,
    )

    ev = EvidenceMapper.create_from_words(
        field_name="invoice_number",
        extracted_value="INV-2024-001",
        words=[w1, w2],
        page_number=1,
    )

    assert ev.bounding_box is not None
    assert ev.bounding_box.x0 == 10.0
    assert ev.bounding_box.x1 == 70.0
    assert ev.source_method == "ocr"
    assert ev.ocr_confidence == 0.93


@pytest.mark.unit
def test_create_missing_evidence() -> None:
    """Verify missing field evidence representation."""
    ev = EvidenceMapper.create_missing_evidence(
        field_name="tax",
        reason="Tax omitted from invoice",
    )
    assert ev.status == EvidenceStatus.MISSING
    assert ev.extracted_value is None
    assert ev.bounding_box is None
    assert ev.confidence == 0.0


@pytest.mark.unit
def test_validate_bounding_box() -> None:
    """Verify bounding box containment and inversion checks."""
    valid_box = BoundingBox(page=1, x0=10.0, y0=10.0, x1=500.0, y1=700.0)
    is_valid, msg = EvidenceMapper.validate_bounding_box(valid_box, 595.0, 842.0)
    assert is_valid
    assert msg is None

    exceed_box = BoundingBox(page=1, x0=10.0, y0=10.0, x1=650.0, y1=700.0)
    is_valid2, msg2 = EvidenceMapper.validate_bounding_box(exceed_box, 595.0, 842.0)
    assert not is_valid2
    assert "exceeds" in (msg2 or "")

    inverted_box = BoundingBox(page=1, x0=100.0, y0=10.0, x1=50.0, y1=700.0)
    is_valid3, msg3 = EvidenceMapper.validate_bounding_box(inverted_box, 595.0, 842.0)
    assert not is_valid3
    assert "Inverted" in (msg3 or "")
