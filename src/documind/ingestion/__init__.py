"""Ingestion module for DocuMind.

Coordinates document receipt, deep content validation, metadata generation,
and isolated atomic storage.
"""

from documind.ingestion.file_validation import extract_file_bytes, validate_pdf
from documind.ingestion.models import (
    IngestionMetadata,
    IngestionResult,
    IngestionStatus,
    ValidationDetail,
)
from documind.ingestion.service import IngestionService
from documind.ingestion.storage import StorageManager, sanitize_filename

__all__ = [
    "IngestionMetadata",
    "IngestionResult",
    "IngestionService",
    "IngestionStatus",
    "StorageManager",
    "ValidationDetail",
    "extract_file_bytes",
    "sanitize_filename",
    "validate_pdf",
]
