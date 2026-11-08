"""Exception hierarchy for DocuMind.

Defines standardized exceptions across all pipeline stages to support
clear error handling, diagnostics, and graceful degradation.
"""


class DocuMindError(Exception):
    """Base exception for all DocuMind errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ConfigurationError(DocuMindError):
    """Raised when configuration parameters or environment variables are invalid."""


class IngestionError(DocuMindError):
    """Base exception for file ingestion, validation, or storage failures."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when an ingested file has an unsupported MIME type or extension."""


class FileSizeExceededError(IngestionError):
    """Raised when an uploaded document exceeds the maximum allowable size."""


class EmptyFileError(IngestionError):
    """Raised when an ingested document is 0 bytes."""


class FileSignatureError(IngestionError):
    """Raised when the binary file signature (magic bytes) does not match the expected format."""


class CorruptedPDFError(IngestionError):
    """Raised when a PDF file is structurally malformed or unparseable."""


class EncryptedPDFError(IngestionError):
    """Raised when an ingested PDF is password-protected or encrypted contrary to policy."""


class PageCountExceededError(IngestionError):
    """Raised when an ingested PDF exceeds the maximum permitted page count."""


class StorageError(IngestionError):
    """Raised when a filesystem or storage operation fails."""


class PathTraversalError(StorageError):
    """Raised when an uploaded filename or path contains traversal sequences."""


class ExtractionError(DocuMindError):
    """Base exception for extraction failures (native PDF text, OCR, parsing)."""


class OCRError(ExtractionError):
    """Raised when optical character recognition fails or engine is unavailable."""


class ValidationError(DocuMindError):
    """Base exception for schema or business rule validation failures."""


class SchemaValidationError(ValidationError):
    """Raised when extracted data fails structural schema requirements."""


class BusinessRuleError(ValidationError):
    """Raised when extracted data violates arithmetic or domain constraints."""


class MatchingError(DocuMindError):
    """Raised when reference-record or purchase-order matching fails."""


class ReviewError(DocuMindError):
    """Raised during human review, correction submission, or state transition."""


class ReportingError(DocuMindError):
    """Raised when export or report generation fails."""
