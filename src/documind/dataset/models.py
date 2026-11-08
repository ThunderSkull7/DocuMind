"""Data models for synthetic invoice annotations and dataset manifest."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    """Format category of the generated invoice."""

    DIGITAL = "digital"
    SCANNED = "scanned"


class IssueType(str, Enum):
    """Categorization of deliberately introduced challenges in synthetic invoices."""

    MISSING_FIELD = "missing_field"
    AMBIGUOUS_DATE = "ambiguous_date"
    INCONSISTENT_DATES = "inconsistent_dates"
    ARITHMETIC_MISMATCH = "arithmetic_mismatch"
    UNUSUAL_NUMBER_FORMAT = "unusual_number_format"
    SIMILAR_LOOKING_CHARS = "similar_looking_chars"
    DUPLICATE_IDENTIFIER = "duplicate_identifier"
    SCAN_DEGRADATION = "scan_degradation"
    SCAN_SKEW = "scan_skew"


class IntroducedIssue(BaseModel):
    """Specification of an intentional edge case or anomaly embedded in the document."""

    model_config = ConfigDict(extra="forbid")

    issue_type: IssueType = Field(
        ..., description="Classification of the introduced defect or variance"
    )
    field: str | None = Field(default=None, description="Affected field name if field-specific")
    description: str = Field(
        ..., description="Explanation of why and how this issue was introduced"
    )
    expected_extracted: str | None = Field(
        default=None, description="What an extractor reading raw text would observe"
    )
    ground_truth_actual: str | None = Field(
        default=None, description="Ground truth logical semantic value"
    )


class DocumentCharacteristics(BaseModel):
    """Visual and layout properties of the generated document."""

    model_config = ConfigDict(extra="forbid")

    layout_template: str = Field(
        ..., description="Layout identifier (e.g. modern_tech, corporate_classic)"
    )
    page_count: int = Field(default=1, ge=1, description="Number of pages in the generated PDF")
    is_scanned: bool = Field(
        default=False, description="Whether document is image-based without text layer"
    )
    resolution_dpi: int = Field(default=300, description="DPI used during rendering or simulation")
    rotation_degrees: float = Field(default=0.0, description="Skew angle applied to scanned image")
    jpeg_quality: int | None = Field(
        default=None, description="JPEG compression quality if scanned"
    )
    contrast_factor: float = Field(default=1.0, description="Contrast scaling factor")


class SyntheticInvoiceAnnotation(BaseModel):
    """Gold-standard annotation for a synthetic invoice.

    Strictly separates ground truth expected values from introduced issues
    and document characteristics.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., description="Unique corpus document ID (e.g. DOC-SYN-001)")
    file_name: str = Field(..., description="PDF filename")
    document_type: DocumentType = Field(..., description="digital or scanned")

    # Core Invoice Ground Truth (None if intentionally missing)
    invoice_number: str | None = Field(
        default=None, description="Ground truth invoice number or None if missing"
    )
    invoice_date: str | None = Field(
        default=None, description="ISO-8601 date string (YYYY-MM-DD) or None if missing"
    )
    vendor_name: str | None = Field(
        default=None, description="Ground truth vendor name or None if missing"
    )
    currency: str | None = Field(default=None, description="Ground truth ISO 4217 code or symbol")
    subtotal: str | None = Field(default=None, description="Decimal string representation or None")
    tax: str | None = Field(default=None, description="Decimal string representation or None")
    total: str | None = Field(default=None, description="Decimal string representation or None")

    # Metadata & Characteristics
    characteristics: DocumentCharacteristics = Field(
        ..., description="Rendering and layout characteristics"
    )
    deliberately_introduced_issues: list[IntroducedIssue] = Field(
        default_factory=list,
        description="Explicit registry of deliberate edge cases",
    )


class ManifestDocumentEntry(BaseModel):
    """Entry in the dataset manifest summarizing a single corpus document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    file_name: str
    relative_path: str
    annotation_path: str
    sha256_hash: str
    document_type: DocumentType
    page_count: int
    characteristics: DocumentCharacteristics
    issues_count: int


class DatasetManifest(BaseModel):
    """Complete catalog and provenance manifest for the synthetic invoice corpus."""

    model_config = ConfigDict(extra="forbid")

    dataset_version: str = Field(default="1.0.0", description="Semver of dataset release")
    created_at: datetime = Field(..., description="Timestamp of dataset generation")
    generation_seed: int = Field(
        default=42, description="Random seed used for deterministic reproduction"
    )
    total_documents: int = Field(..., ge=1, description="Total documents in corpus (target 50)")
    digital_count: int = Field(..., ge=0, description="Count of digital text PDFs (target 30)")
    scanned_count: int = Field(
        ..., ge=0, description="Count of image-based scanned PDFs (target 20)"
    )
    documents: list[ManifestDocumentEntry] = Field(..., description="List of all catalog entries")
