"""Data models for document ingestion and file validation metadata."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IngestionStatus(str, Enum):
    """Lifecycle status of a document ingestion attempt."""

    SUCCESS = "success"
    REJECTED = "rejected"
    FAILED = "failed"


class ValidationDetail(BaseModel):
    """Fine-grained audit of validation checks executed on an ingested file."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool = Field(..., description="Whether all mandatory validation gates passed")
    file_extension: str = Field(..., description="File extension extracted from filename")
    detected_mime: str = Field(..., description="MIME type detected or confirmed")
    file_size_bytes: int = Field(..., ge=0, description="Exact file size in bytes")
    page_count: int | None = Field(
        default=None, ge=0, description="Total document pages if parseable"
    )
    is_encrypted: bool = Field(
        default=False, description="Whether document requires password or is encrypted"
    )
    errors: list[str] = Field(
        default_factory=list, description="Validation failure messages if any"
    )
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warning notices")


class IngestionMetadata(BaseModel):
    """Structured audit metadata for an ingested document.

    Separates transport and storage tracking from domain extraction fields.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., description="Unique internal identifier (UUIDv4) for document")
    original_filename: str = Field(..., description="Original client-supplied filename")
    sanitized_filename: str = Field(
        ..., description="Safe filename stripped of directory separators and symbols"
    )
    storage_path: str | None = Field(
        default=None, description="Storage location relative to storage root"
    )
    file_size_bytes: int = Field(..., ge=0, description="Size in bytes")
    sha256_hash: str = Field(
        ..., min_length=64, max_length=64, description="Cryptographic SHA-256 digest"
    )
    page_count: int = Field(default=0, ge=0, description="Number of pages in PDF document")
    mime_type: str = Field(default="application/pdf", description="MIME type of stored document")
    upload_timestamp: datetime = Field(..., description="UTC timestamp of ingestion")
    status: IngestionStatus = Field(..., description="Outcome status of ingestion request")
    validation: ValidationDetail = Field(..., description="Detailed validation breakdown")


class IngestionResult(BaseModel):
    """Standardized response container returned by IngestionService."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(..., description="True if document was validated and safely stored")
    metadata: IngestionMetadata = Field(..., description="Comprehensive ingestion metadata")
    error_message: str | None = Field(
        default=None, description="High-level error summary if unsuccessful"
    )
