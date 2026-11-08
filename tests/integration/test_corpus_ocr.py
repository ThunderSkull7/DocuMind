"""Integration tests verifying full corpus extraction: all 30 digital PDFs and all 20 scanned PDFs."""

from pathlib import Path

import pytest

from documind.dataset.models import DatasetManifest, DocumentType
from documind.extraction.models import (
    ExtractionStatus,
    OverallExtractionMethod,
    PageExtractionMethod,
)
from documind.extraction.ocr import is_tesseract_available
from documind.extraction.service import ExtractionService


@pytest.fixture(scope="module")
def manifest() -> DatasetManifest:
    """Load dataset manifest."""
    manifest_path = Path("data/manifest.json")
    return DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def extraction_service() -> ExtractionService:
    """Provide ExtractionService instance."""
    return ExtractionService()


@pytest.mark.integration
def test_all_30_digital_corpus_extractions(
    manifest: DatasetManifest, extraction_service: ExtractionService
) -> None:
    """Verify that all 30 digital PDFs extract native text with valid coordinates and zero OCR fallback."""
    digital_entries = [d for d in manifest.documents if d.document_type == DocumentType.DIGITAL]
    assert len(digital_entries) == 30

    for entry in digital_entries:
        pdf_path = Path("data/synthetic_documents") / entry.file_name
        assert pdf_path.is_file()

        result = extraction_service.extract_from_bytes(
            content=pdf_path.read_bytes(),
            document_id=entry.document_id,
            source_file_hash=entry.sha256_hash,
        )

        assert result.extraction_status == ExtractionStatus.SUCCESS, (
            f"{entry.document_id} extraction failed: {result.errors}"
        )
        assert result.overall_extraction_method == OverallExtractionMethod.NATIVE_ONLY, (
            f"{entry.document_id} should be NATIVE_ONLY"
        )
        assert len(result.pages) == entry.page_count

        for page in result.pages:
            assert page.extraction_method == PageExtractionMethod.NATIVE_TEXT
            assert page.character_count >= 300, f"{entry.document_id} page has low char count"
            assert page.word_count >= 40, f"{entry.document_id} page has low word count"
            assert page.normalized_text != ""

            # Verify spatial text blocks and words
            assert len(page.text_blocks) > 0
            for block in page.text_blocks:
                assert 0.0 <= block.bounding_box.x0 <= block.bounding_box.x1 <= page.page_width
                assert 0.0 <= block.bounding_box.y0 <= block.bounding_box.y1 <= page.page_height
                for word in block.words:
                    assert (
                        word.confidence is None
                    )  # Native text must explicitly have None confidence
                    assert 0.0 <= word.bounding_box.x0 <= word.bounding_box.x1 <= page.page_width
                    assert 0.0 <= word.bounding_box.y0 <= word.bounding_box.y1 <= page.page_height


@pytest.mark.integration
@pytest.mark.ocr
def test_all_20_scanned_corpus_extractions(
    manifest: DatasetManifest, extraction_service: ExtractionService
) -> None:
    """Verify that all 20 scanned PDFs route to OCR, extract non-empty text, valid bboxes, and confidence."""
    if not is_tesseract_available():
        pytest.skip("Tesseract OCR binary not installed; skipping live OCR corpus verification.")

    scanned_entries = [d for d in manifest.documents if d.document_type == DocumentType.SCANNED]
    assert len(scanned_entries) == 20

    for entry in scanned_entries:
        pdf_path = Path("data/synthetic_documents") / entry.file_name
        assert pdf_path.is_file()

        result = extraction_service.extract_from_bytes(
            content=pdf_path.read_bytes(),
            document_id=entry.document_id,
            source_file_hash=entry.sha256_hash,
        )

        assert result.extraction_status == ExtractionStatus.SUCCESS, (
            f"{entry.document_id} OCR failed: {result.errors}"
        )
        assert result.overall_extraction_method == OverallExtractionMethod.OCR_ONLY, (
            f"{entry.document_id} should be OCR_ONLY"
        )
        assert len(result.pages) == entry.page_count
        assert len(result.errors) == 0

        for page in result.pages:
            assert page.extraction_method == PageExtractionMethod.OCR
            assert page.character_count > 300, (
                f"{entry.document_id} OCR produced insufficient characters: {page.character_count}"
            )
            assert page.word_count > 40, (
                f"{entry.document_id} OCR produced insufficient words: {page.word_count}"
            )
            assert page.normalized_text != ""

            # Verify spatial text blocks and words
            assert len(page.text_blocks) > 0
            for block in page.text_blocks:
                assert 0.0 <= block.bounding_box.x0 <= block.bounding_box.x1 <= page.page_width
                assert 0.0 <= block.bounding_box.y0 <= block.bounding_box.y1 <= page.page_height
                for word in block.words:
                    assert word.confidence is not None  # OCR must populate engine confidence
                    assert 0.0 <= word.confidence <= 1.0
                    assert 0.0 <= word.bounding_box.x0 <= word.bounding_box.x1 <= page.page_width
                    assert 0.0 <= word.bounding_box.y0 <= word.bounding_box.y1 <= page.page_height
