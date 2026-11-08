"""Integration tests for IngestionService end-to-end workflow."""

import io
from pathlib import Path

import pytest

from documind.config import Settings
from documind.ingestion.models import IngestionStatus
from documind.ingestion.service import IngestionService
from documind.ingestion.storage import StorageManager


@pytest.fixture
def isolated_service(temp_dir: Path) -> IngestionService:
    """Provide an IngestionService configured with an isolated storage path."""
    settings = Settings(
        project_root=temp_dir,
        DOCUMIND_STORAGE_DIR="isolated_storage",
    )
    storage = StorageManager(settings)
    return IngestionService(settings=settings, storage_manager=storage)


@pytest.mark.integration
def test_ingest_digital_pdf(isolated_service: IngestionService) -> None:
    """Verify end-to-end ingestion of a digital PDF from the synthetic corpus."""
    corpus_pdf = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    assert corpus_pdf.is_file()

    result = isolated_service.ingest(
        file_input=corpus_pdf,
        original_filename="incoming_digital_invoice.pdf",
    )

    assert result.success
    assert result.metadata.status == IngestionStatus.SUCCESS
    assert result.metadata.page_count == 1
    assert result.metadata.storage_path is not None

    # Verify persisted metadata
    stored_meta = isolated_service.get_ingested_metadata(result.metadata.document_id)
    assert stored_meta is not None
    assert stored_meta.document_id == result.metadata.document_id
    assert stored_meta.sha256_hash == result.metadata.sha256_hash

    # Verify stored file content matches source
    stored_file = isolated_service.storage.retrieve(result.metadata.document_id)
    assert stored_file is not None
    assert stored_file.read_bytes() == corpus_pdf.read_bytes()


@pytest.mark.integration
def test_ingest_scanned_pdf(isolated_service: IngestionService) -> None:
    """Verify end-to-end ingestion of an image-based scanned PDF."""
    scanned_pdf = Path("data/synthetic_documents/syn_invoice_031_scanned.pdf")
    assert scanned_pdf.is_file()

    result = isolated_service.ingest(
        file_input=scanned_pdf,
        original_filename="incoming_scanned_invoice.pdf",
    )

    assert result.success
    assert result.metadata.status == IngestionStatus.SUCCESS
    assert result.metadata.page_count == 1


@pytest.mark.integration
def test_rejected_document_not_stored(isolated_service: IngestionService) -> None:
    """Verify invalid document is rejected and no file is committed to storage."""
    invalid_payload = b"PlainTextSpoofingPDF"
    result = isolated_service.ingest(
        file_input=invalid_payload,
        original_filename="corrupt_spoof.pdf",
    )

    assert not result.success
    assert result.metadata.status == IngestionStatus.REJECTED
    assert result.error_message is not None

    # Confirm no file exists in storage for this rejected document
    stored_file = isolated_service.storage.retrieve(result.metadata.document_id)
    assert stored_file is None


@pytest.mark.integration
def test_ingest_from_stream(isolated_service: IngestionService) -> None:
    """Verify ingestion accepts stream-like objects (e.g. Streamlit UploadedFile)."""
    corpus_pdf = Path("data/synthetic_documents/syn_invoice_002_digital.pdf")
    stream = io.BytesIO(corpus_pdf.read_bytes())

    result = isolated_service.ingest(
        file_input=stream,
        original_filename="uploaded_stream.pdf",
    )

    assert result.success
    assert result.metadata.status == IngestionStatus.SUCCESS
    assert result.metadata.sha256_hash == isolated_service.storage.calculate_sha256(
        corpus_pdf.read_bytes()
    )
