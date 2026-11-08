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


class TesseractNotFoundError(OCRError):
    """Raised when Tesseract OCR binary cannot be located on system PATH or configured path."""


class OCRTimeoutError(OCRError):
    """Raised when an OCR operation exceeds the configured execution timeout."""


class PDFExtractionError(ExtractionError):
    """Raised when native PDF text extraction encounters a structural or parser error."""


class PageExtractionError(ExtractionError):
    """Raised when processing fails on an individual document page."""


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


class InvalidStateTransitionError(ReviewError):
    """Raised when an illegal review state transition is attempted."""


class ReviewConcurrencyError(ReviewError):
    """Raised when an update conflicts with the current review revision (optimistic locking)."""


class ReviewNotFoundError(ReviewError):
    """Raised when a requested review record cannot be found."""


class DuplicateActiveReviewError(ReviewError):
    """Raised when attempting to create a second active review for a document."""


class InvalidCorrectionError(ReviewError):
    """Raised when a proposed field correction fails validation or reason requirements."""


class UnresolvedDiscrepancyError(ReviewError):
    """Raised when approval is attempted on a document with blocking unresolved discrepancies."""


class ReportingError(DocuMindError):
    """Raised when export or report generation fails."""
