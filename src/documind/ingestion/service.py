"""Ingestion service coordinating validation, metadata, and secure storage."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from documind.config import Settings, get_settings
from documind.ingestion.file_validation import extract_file_bytes, validate_pdf
from documind.ingestion.models import (
    IngestionMetadata,
    IngestionResult,
    IngestionStatus,
)
from documind.ingestion.storage import StorageManager, sanitize_filename
from documind.logging import get_logger

UTC = timezone.utc
logger = get_logger("ingestion.service")


class IngestionService:
    """Coordinates validation, metadata generation, and isolated storage for documents."""

    def __init__(
        self,
        settings: Settings | None = None,
        storage_manager: StorageManager | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage_manager or StorageManager(self.settings)

    def ingest(
        self,
        file_input: bytes | Path | str | BinaryIO,
        original_filename: str,
        document_id: str | None = None,
    ) -> IngestionResult:
        """Ingest, validate, and securely store an incoming document.

        Args:
            file_input: Binary content, file path, or file-like object.
            original_filename: Original filename submitted with the upload.
            document_id: Optional designated document ID (auto-generated if None).

        Returns:
            IngestionResult containing success flag, metadata, and error details.
        """
        upload_time = datetime.now(UTC)
        doc_id = document_id or self.storage.generate_document_id()
        safe_name = sanitize_filename(original_filename)

        # 1. Read content
        try:
            content = extract_file_bytes(file_input)
        except Exception as exc:
            logger.warning(f"Failed to extract bytes for upload '{original_filename}': {exc}")
            validation = validate_pdf(b"", filename=original_filename, settings=self.settings)
            metadata = IngestionMetadata(
                document_id=doc_id,
                original_filename=original_filename,
                sanitized_filename=safe_name,
                storage_path=None,
                file_size_bytes=0,
                sha256_hash="0" * 64,
                page_count=0,
                mime_type="unknown",
                upload_timestamp=upload_time,
                status=IngestionStatus.REJECTED,
                validation=validation,
            )
            return IngestionResult(
                success=False,
                metadata=metadata,
                error_message=f"Could not read upload payload: {exc}",
            )

        sha256_hash = self.storage.calculate_sha256(content)

        # 2. Validation
        validation = validate_pdf(
            file_input=content,
            filename=original_filename,
            settings=self.settings,
            raise_on_error=False,
        )

        if not validation.is_valid:
            error_summary = "; ".join(validation.errors)
            logger.warning(
                f"Document '{original_filename}' (id={doc_id}) rejected. Reasons: {error_summary}"
            )
            metadata = IngestionMetadata(
                document_id=doc_id,
                original_filename=original_filename,
                sanitized_filename=safe_name,
                storage_path=None,
                file_size_bytes=len(content),
                sha256_hash=sha256_hash,
                page_count=validation.page_count or 0,
                mime_type=validation.detected_mime,
                upload_timestamp=upload_time,
                status=IngestionStatus.REJECTED,
                validation=validation,
            )
            return IngestionResult(
                success=False,
                metadata=metadata,
                error_message=f"Validation failed: {error_summary}",
            )

        # 3. Secure Atomic Storage
        try:
            _, _, stored_hash, target_path = self.storage.store(
                content=content,
                original_filename=original_filename,
                document_id=doc_id,
            )
            # Portable relative path
            try:
                rel_path = str(target_path.relative_to(self.settings.project_root)).replace(
                    "\\", "/"
                )
            except ValueError:
                rel_path = str(target_path).replace("\\", "/")

            metadata = IngestionMetadata(
                document_id=doc_id,
                original_filename=original_filename,
                sanitized_filename=safe_name,
                storage_path=rel_path,
                file_size_bytes=len(content),
                sha256_hash=stored_hash,
                page_count=validation.page_count or 1,
                mime_type=validation.detected_mime,
                upload_timestamp=upload_time,
                status=IngestionStatus.SUCCESS,
                validation=validation,
            )

            # Persist ingestion metadata json alongside stored document
            metadata_file = target_path.parent / "metadata.json"
            metadata_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

            logger.info(f"Successfully ingested document '{original_filename}' as id={doc_id}")
            return IngestionResult(
                success=True,
                metadata=metadata,
                error_message=None,
            )

        except Exception as exc:
            logger.error(f"Storage failure for document id={doc_id}: {exc}")
            metadata = IngestionMetadata(
                document_id=doc_id,
                original_filename=original_filename,
                sanitized_filename=safe_name,
                storage_path=None,
                file_size_bytes=len(content),
                sha256_hash=sha256_hash,
                page_count=validation.page_count or 0,
                mime_type=validation.detected_mime,
                upload_timestamp=upload_time,
                status=IngestionStatus.FAILED,
                validation=validation,
            )
            return IngestionResult(
                success=False,
                metadata=metadata,
                error_message=f"Storage operation failed: {exc}",
            )

    def get_ingested_metadata(self, document_id: str) -> IngestionMetadata | None:
        """Retrieve stored metadata for a document ID if present."""
        doc_dir = self.storage.get_document_dir(document_id)
        meta_file = doc_dir / "metadata.json"
        if meta_file.is_file():
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                return IngestionMetadata.model_validate(data)
            except Exception:
                return None
        return None
