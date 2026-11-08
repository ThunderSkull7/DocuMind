"""Integration tests for ExtractionService end-to-end pipeline."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from documind.config import Settings
from documind.extraction.models import (
    ExtractionStatus,
    OverallExtractionMethod,
    PageExtraction,
    PageExtractionMethod,
)
from documind.extraction.ocr import OCREngine
from documind.extraction.service import ExtractionService
from documind.ingestion.service import IngestionService
from documind.ingestion.storage import StorageManager


@pytest.fixture
def mock_ocr_service(temp_dir: Path) -> tuple[ExtractionService, IngestionService]:
    """Provide an isolated IngestionService and ExtractionService with mocked OCR."""
    settings = Settings(
        project_root=temp_dir,
        DOCUMIND_STORAGE_DIR="test_storage",
        ocr_enabled=True,
    )
    storage = StorageManager(settings)
    ingestion = IngestionService(settings=settings, storage_manager=storage)

    mock_engine = MagicMock(spec=OCREngine)

    def fake_extract_page(page, page_number: int) -> PageExtraction:
        return PageExtraction(
            page_number=page_number,
            extraction_method=PageExtractionMethod.OCR,
            raw_text="RECOGNIZED OCR INVOICE CONTENT",
            normalized_text="RECOGNIZED OCR INVOICE CONTENT",
            text_blocks=[],
            word_count=4,
            character_count=30,
            page_width=float(page.rect.width),
            page_height=float(page.rect.height),
            quality=None,
            warnings=[],
        )

    mock_engine.extract_page_ocr.side_effect = fake_extract_page

    extraction = ExtractionService(
        settings=settings,
        storage_manager=storage,
        ingestion_service=ingestion,
        ocr_engine=mock_engine,
    )
    return extraction, ingestion


@pytest.mark.integration
def test_extract_ingested_digital_document(
    mock_ocr_service: tuple[ExtractionService, IngestionService],
) -> None:
    """Verify end-to-end ingestion and native extraction of a digital invoice."""
    extraction_svc, ingestion_svc = mock_ocr_service
    corpus_pdf = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")

    # Ingest document
    ingest_res = ingestion_svc.ingest(corpus_pdf, "digital_invoice.pdf")
    assert ingest_res.success
    doc_id = ingest_res.metadata.document_id

    # Extract document
    extract_res = extraction_svc.extract_document(
        document_id=doc_id,
        expected_hash=ingest_res.metadata.sha256_hash,
    )

    assert extract_res.extraction_status == ExtractionStatus.SUCCESS
    assert extract_res.overall_extraction_method == OverallExtractionMethod.NATIVE_ONLY
    assert extract_res.total_pages == 1
    assert len(extract_res.pages) == 1
    assert "INVOICE" in extract_res.pages[0].raw_text
    assert extract_res.pages[0].extraction_method == PageExtractionMethod.NATIVE_TEXT
    assert extract_res.processing_duration_ms > 0.0
    assert "pymupdf_version" in extract_res.engine_metadata


@pytest.mark.integration
def test_extract_ingested_scanned_document_routes_to_ocr(
    mock_ocr_service: tuple[ExtractionService, IngestionService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify end-to-end ingestion and OCR fallback of a scanned invoice."""
    monkeypatch.setattr("documind.extraction.routing.is_tesseract_available", lambda *_: True)
    extraction_svc, ingestion_svc = mock_ocr_service
    scanned_pdf = Path("data/synthetic_documents/syn_invoice_031_scanned.pdf")

    # Ingest scanned document
    ingest_res = ingestion_svc.ingest(scanned_pdf, "scanned_invoice.pdf")
    assert ingest_res.success
    doc_id = ingest_res.metadata.document_id

    # Extract document
    extract_res = extraction_svc.extract_document(
        document_id=doc_id,
        expected_hash=ingest_res.metadata.sha256_hash,
    )

    assert extract_res.extraction_status == ExtractionStatus.SUCCESS
    assert extract_res.overall_extraction_method == OverallExtractionMethod.OCR_ONLY
    assert extract_res.total_pages == 1
    assert extract_res.pages[0].extraction_method == PageExtractionMethod.OCR
    assert "RECOGNIZED OCR" in extract_res.pages[0].raw_text


@pytest.mark.integration
def test_hash_mismatch_detection(
    mock_ocr_service: tuple[ExtractionService, IngestionService],
) -> None:
    """Verify hash mismatch is caught and aborts extraction."""
    extraction_svc, ingestion_svc = mock_ocr_service
    corpus_pdf = Path("data/synthetic_documents/syn_invoice_002_digital.pdf")

    ingest_res = ingestion_svc.ingest(corpus_pdf, "digital_invoice.pdf")
    doc_id = ingest_res.metadata.document_id

    bogus_hash = "f" * 64
    extract_res = extraction_svc.extract_document(
        document_id=doc_id,
        expected_hash=bogus_hash,
    )

    assert extract_res.extraction_status == ExtractionStatus.FAILED
    assert any("integrity verification failed" in err for err in extract_res.errors)


@pytest.mark.integration
def test_missing_document_handling(
    mock_ocr_service: tuple[ExtractionService, IngestionService],
) -> None:
    """Verify attempting extraction on a non-existent document ID returns FAILED result."""
    extraction_svc, _ = mock_ocr_service
    extract_res = extraction_svc.extract_document("non-existent-uuid-12345")

    assert extract_res.extraction_status == ExtractionStatus.FAILED
    assert any("not found in storage" in err for err in extract_res.errors)


@pytest.mark.integration
def test_multipage_document_processing(
    mock_ocr_service: tuple[ExtractionService, IngestionService],
) -> None:
    """Verify multipage documents are extracted with all pages present."""
    extraction_svc, ingestion_svc = mock_ocr_service
    multipage_pdf = Path("data/synthetic_documents/syn_invoice_010_digital.pdf")

    ingest_res = ingestion_svc.ingest(multipage_pdf, "multipage.pdf")
    doc_id = ingest_res.metadata.document_id

    extract_res = extraction_svc.extract_document(doc_id)

    assert extract_res.extraction_status == ExtractionStatus.SUCCESS
    assert extract_res.total_pages == 2
    assert len(extract_res.pages) == 2
    assert extract_res.pages[0].page_number == 1
    assert extract_res.pages[1].page_number == 2
    assert extract_res.pages[0].extraction_method == PageExtractionMethod.NATIVE_TEXT
    assert extract_res.pages[1].extraction_method == PageExtractionMethod.NATIVE_TEXT
