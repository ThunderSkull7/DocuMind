"""Unit tests for ingestion file validation subsystem."""

import io
from pathlib import Path

import pymupdf
import pytest

from documind.config import Settings
from documind.exceptions import (
    CorruptedPDFError,
    EmptyFileError,
    EncryptedPDFError,
    FileSignatureError,
    FileSizeExceededError,
    PageCountExceededError,
    UnsupportedFileTypeError,
)
from documind.ingestion.file_validation import validate_pdf


@pytest.fixture
def sample_valid_pdf_bytes() -> bytes:
    """Generate minimal valid PDF in memory."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Valid invoice test content")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def sample_encrypted_pdf_bytes() -> bytes:
    """Generate password-protected encrypted PDF in memory."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Secret confidential invoice")
    # Encrypt document with owner/user password
    perm = int(
        pymupdf.PDF_PERM_ACCESSIBILITY
        | pymupdf.PDF_PERM_PRINT
        | pymupdf.PDF_PERM_COPY
        | pymupdf.PDF_PERM_ANNOTATE
    )
    encrypt_meth = pymupdf.PDF_ENCRYPT_AES_256
    pdf_bytes = doc.tobytes(
        encryption=encrypt_meth,
        owner_pw="owner123",
        user_pw="user123",
        permissions=perm,
    )
    doc.close()
    return pdf_bytes


@pytest.mark.unit
def test_valid_digital_pdf(sample_valid_pdf_bytes: bytes) -> None:
    """Verify standard valid PDF passes all validation checks."""
    result = validate_pdf(sample_valid_pdf_bytes, "valid_invoice.pdf")
    assert result.is_valid
    assert result.page_count == 1
    assert result.detected_mime == "application/pdf"
    assert not result.errors


@pytest.mark.unit
def test_valid_scanned_pdf() -> None:
    """Verify generated scanned PDF from corpus passes file validation."""
    scanned_path = Path("data/synthetic_documents/syn_invoice_031_scanned.pdf")
    assert scanned_path.is_file()
    result = validate_pdf(scanned_path, scanned_path.name)
    assert result.is_valid
    assert result.page_count == 1


@pytest.mark.unit
def test_unsupported_file_extension(sample_valid_pdf_bytes: bytes) -> None:
    """Verify non-.pdf extension is rejected."""
    result = validate_pdf(sample_valid_pdf_bytes, "invoice.docx")
    assert not result.is_valid
    assert any("extension" in err.lower() for err in result.errors)

    with pytest.raises(UnsupportedFileTypeError):
        validate_pdf(sample_valid_pdf_bytes, "invoice.png", raise_on_error=True)


@pytest.mark.unit
def test_empty_file() -> None:
    """Verify 0-byte file is rejected as empty."""
    result = validate_pdf(b"", "empty.pdf")
    assert not result.is_valid
    assert any("empty" in err.lower() for err in result.errors)

    with pytest.raises(EmptyFileError):
        validate_pdf(b"", "empty.pdf", raise_on_error=True)


@pytest.mark.unit
def test_renamed_non_pdf_file() -> None:
    """Verify arbitrary binary/text renamed to .pdf fails signature check."""
    fake_content = b"This is plain text content pretending to be a PDF."
    result = validate_pdf(fake_content, "invoice_fake.pdf")
    assert not result.is_valid
    assert any("signature" in err.lower() for err in result.errors)

    with pytest.raises(FileSignatureError):
        validate_pdf(fake_content, "invoice_fake.pdf", raise_on_error=True)


@pytest.mark.unit
def test_oversized_file(temp_dir: Path) -> None:
    """Verify file exceeding max_upload_size_mb is rejected."""
    # Configure tiny 1MB limit for testing
    settings = Settings(
        project_root=temp_dir,
        max_upload_size_mb=1,
    )
    # Create 1.5MB dummy content with PDF magic header
    oversized = b"%PDF-1.7\n" + (b"0" * (1024 * 1024 + 500000))
    result = validate_pdf(oversized, "large.pdf", settings=settings)
    assert not result.is_valid
    assert any("exceeds" in err.lower() for err in result.errors)

    with pytest.raises(FileSizeExceededError):
        validate_pdf(oversized, "large.pdf", settings=settings, raise_on_error=True)


@pytest.mark.unit
def test_excessive_page_count(temp_dir: Path) -> None:
    """Verify PDF exceeding max_page_count is rejected."""
    settings = Settings(
        project_root=temp_dir,
        max_page_count=3,
    )
    doc = pymupdf.open()
    for _ in range(5):
        doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    result = validate_pdf(pdf_bytes, "many_pages.pdf", settings=settings)
    assert not result.is_valid
    assert any("page count" in err.lower() for err in result.errors)

    with pytest.raises(PageCountExceededError):
        validate_pdf(pdf_bytes, "many_pages.pdf", settings=settings, raise_on_error=True)


@pytest.mark.unit
def test_encrypted_pdf_rejected_by_policy(
    sample_encrypted_pdf_bytes: bytes, temp_dir: Path
) -> None:
    """Verify password-encrypted PDF is rejected according to policy."""
    settings = Settings(
        project_root=temp_dir,
        allow_encrypted_pdfs=False,
    )
    result = validate_pdf(sample_encrypted_pdf_bytes, "encrypted.pdf", settings=settings)
    assert not result.is_valid
    assert any("encrypted" in err.lower() for err in result.errors)

    with pytest.raises(EncryptedPDFError):
        validate_pdf(
            sample_encrypted_pdf_bytes, "encrypted.pdf", settings=settings, raise_on_error=True
        )


@pytest.mark.unit
def test_corrupted_pdf_structure() -> None:
    """Verify file with valid header but corrupted trailer/xref fails parser check."""
    corrupted = b"%PDF-1.5\nRandom broken trailer and damaged objects..."
    result = validate_pdf(corrupted, "corrupt.pdf")
    assert not result.is_valid
    assert any("corrupted" in err.lower() or "parsing" in err.lower() for err in result.errors)

    with pytest.raises(CorruptedPDFError):
        validate_pdf(corrupted, "corrupt.pdf", raise_on_error=True)


@pytest.mark.unit
def test_stream_input(sample_valid_pdf_bytes: bytes) -> None:
    """Verify BytesIO stream input is properly validated and seek position preserved."""
    stream = io.BytesIO(sample_valid_pdf_bytes)
    result = validate_pdf(stream, "streamed.pdf")
    assert result.is_valid
    assert stream.tell() == 0  # Position preserved
