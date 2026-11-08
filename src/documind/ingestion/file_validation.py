"""PDF file validation for DocuMind ingestion subsystem.

Enforces deep content inspection, file size bounds, page count limits,
PDF signature verification, and encryption policies.
"""

from pathlib import Path
from typing import BinaryIO

import pymupdf

from documind.config import Settings, get_settings
from documind.exceptions import (
    CorruptedPDFError,
    EmptyFileError,
    EncryptedPDFError,
    FileSignatureError,
    FileSizeExceededError,
    PageCountExceededError,
    UnsupportedFileTypeError,
)
from documind.ingestion.models import ValidationDetail
from documind.logging import get_logger

logger = get_logger("ingestion.file_validation")

PDF_MAGIC_BYTES = b"%PDF-"


def extract_file_bytes(file_input: bytes | Path | str | BinaryIO) -> bytes:
    """Extract raw bytes from various input formats."""
    if isinstance(file_input, bytes):
        return file_input
    if isinstance(file_input, (str, Path)):
        path = Path(file_input)
        if not path.is_file():
            raise UnsupportedFileTypeError(f"File not found: {path}")
        return path.read_bytes()
    if hasattr(file_input, "read"):
        current_pos = file_input.tell() if hasattr(file_input, "tell") else None
        content = file_input.read()
        if current_pos is not None and hasattr(file_input, "seek"):
            file_input.seek(current_pos)
        return content
    raise UnsupportedFileTypeError(f"Unsupported file input type: {type(file_input).__name__}")


def validate_pdf(
    file_input: bytes | Path | str | BinaryIO,
    filename: str,
    settings: Settings | None = None,
    raise_on_error: bool = False,
) -> ValidationDetail:
    """Perform rigorous validation of an uploaded PDF document.

    Checks performed:
    1. Extension verification (.pdf).
    2. Non-empty file constraint (size > 0).
    3. Maximum upload size limit (DOCUMIND_MAX_UPLOAD_SIZE_MB).
    4. Magic bytes signature verification (%PDF-).
    5. Structural parsing compatibility via PyMuPDF.
    6. Encryption and password-protection policy check.
    7. Page count boundaries (1 to DOCUMIND_MAX_PAGE_COUNT).

    Args:
        file_input: Bytes, file path, or stream containing document data.
        filename: Declared original filename.
        settings: Application settings (defaults to get_settings()).
        raise_on_error: If True, raises specific IngestionError instead of returning invalid detail.

    Returns:
        ValidationDetail recording outcome and audit details.
    """
    cfg = settings or get_settings()
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Extension Check
    ext = Path(filename).suffix.lower()
    if ext != ".pdf":
        msg = f"Unsupported file extension '{ext}'. Only .pdf is permitted."
        errors.append(msg)
        if raise_on_error:
            raise UnsupportedFileTypeError(msg)

    # Extract bytes
    try:
        content = extract_file_bytes(file_input)
    except Exception as exc:
        msg = f"Failed to read file content: {exc}"
        errors.append(msg)
        if raise_on_error:
            raise UnsupportedFileTypeError(msg) from exc
        return ValidationDetail(
            is_valid=False,
            file_extension=ext,
            detected_mime="unknown",
            file_size_bytes=0,
            errors=errors,
            warnings=warnings,
        )

    size_bytes = len(content)

    # 2. Empty File Check
    if size_bytes == 0:
        msg = "Uploaded file is 0 bytes (empty document)."
        errors.append(msg)
        if raise_on_error:
            raise EmptyFileError(msg)
        return ValidationDetail(
            is_valid=False,
            file_extension=ext,
            detected_mime="application/x-empty",
            file_size_bytes=0,
            errors=errors,
            warnings=warnings,
        )

    # 3. Maximum Size Check
    max_bytes = cfg.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        msg = (
            f"File size ({size_bytes / (1024 * 1024):.2f} MB) exceeds maximum "
            f"allowed limit of {cfg.max_upload_size_mb} MB."
        )
        errors.append(msg)
        if raise_on_error:
            raise FileSizeExceededError(msg)

    # 4. Signature / Magic Bytes Check
    # PDF specification states %PDF- header must appear within the first 1024 bytes
    header_sample = content[:1024]
    if PDF_MAGIC_BYTES not in header_sample:
        msg = "Invalid file signature: PDF magic header (%PDF-) not found in document header."
        errors.append(msg)
        if raise_on_error:
            raise FileSignatureError(msg)

    # If already failed basic checks, do not attempt to invoke parser
    if errors:
        return ValidationDetail(
            is_valid=False,
            file_extension=ext,
            detected_mime="application/octet-stream",
            file_size_bytes=size_bytes,
            errors=errors,
            warnings=warnings,
        )

    # 5. Parser Compatibility & Structural Integrity Check
    page_count: int | None = None
    is_encrypted = False

    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:
        msg = f"PDF structural parsing failed. Document is corrupted or malformed: {exc}"
        errors.append(msg)
        if raise_on_error:
            raise CorruptedPDFError(msg) from exc
        return ValidationDetail(
            is_valid=False,
            file_extension=ext,
            detected_mime="application/pdf",
            file_size_bytes=size_bytes,
            errors=errors,
            warnings=warnings,
        )

    try:
        # 6. Encryption Check
        if doc.is_encrypted or doc.needs_pass:
            is_encrypted = True
            if not cfg.allow_encrypted_pdfs:
                msg = (
                    "Document is encrypted or password-protected. "
                    "Encrypted PDFs are prohibited by policy."
                )
                errors.append(msg)
                if raise_on_error:
                    raise EncryptedPDFError(msg)

        # 7. Page Count Boundaries
        page_count = len(doc)
        if page_count == 0:
            msg = "Document contains 0 pages."
            errors.append(msg)
            if raise_on_error:
                raise CorruptedPDFError(msg)
        elif page_count > cfg.max_page_count:
            msg = (
                f"Document page count ({page_count}) exceeds allowable "
                f"limit of {cfg.max_page_count} pages."
            )
            errors.append(msg)
            if raise_on_error:
                raise PageCountExceededError(msg)

        # Basic page accessibility check
        if page_count > 0 and not is_encrypted:
            try:
                _ = doc[0].rect
            except Exception as page_exc:
                msg = f"Failed to access document page 0: {page_exc}"
                errors.append(msg)
                if raise_on_error:
                    raise CorruptedPDFError(msg) from page_exc

    finally:
        doc.close()

    is_valid = len(errors) == 0
    return ValidationDetail(
        is_valid=is_valid,
        file_extension=ext,
        detected_mime="application/pdf",
        file_size_bytes=size_bytes,
        page_count=page_count,
        is_encrypted=is_encrypted,
        errors=errors,
        warnings=warnings,
    )
