"""Invoice document schemas and evidence models for DocuMind.

Defines structured representation of invoice fields, evidence provenance,
and extraction records.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ExtractionMethod(str, Enum):
    """Extraction mechanism utilized for retrieving a value."""

    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    RULE_BASED = "rule_based"
    PATTERN = "pattern"
    HUMAN_CORRECTION = "human_correction"


class BoundingBox(BaseModel):
    """Coordinates of a field or token on a document page (normalized or points)."""

    page: int = Field(..., ge=1, description="1-indexed document page number")
    x0: float = Field(..., description="Left coordinate")
    y0: float = Field(..., description="Top coordinate")
    x1: float = Field(..., description="Right coordinate")
    y1: float = Field(..., description="Bottom coordinate")


class FieldEvidence(BaseModel):
    """Provenance and grounding evidence for an extracted field."""

    raw_text: str = Field(..., description="Raw text snippet extracted from document")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)"
    )
    method: ExtractionMethod = Field(..., description="Extraction strategy used")
    bounding_box: BoundingBox | None = Field(
        default=None, description="Spatial coordinates if available"
    )
    page_number: int | None = Field(
        default=None, ge=1, description="Page where evidence was located"
    )


class ExtractedField(BaseModel):
    """Generic wrapper for an extracted field value paired with its grounding evidence."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: str | Decimal | date | None = None
    evidence: FieldEvidence | None = None
    is_valid: bool = True
    error_message: str | None = None


class InvoiceData(BaseModel):
    """Structured invoice fields extracted from a document.

    Initial scope strictly covers core invoice fields:
    - invoice_number (required)
    - invoice_date (required)
    - vendor_name (required)
    - currency (required, standard 3-letter code or symbol)
    - subtotal (optional, but validated against total if present)
    - tax (optional, but validated against total if present)
    - total (required)
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier assigned to the invoice by the vendor",
    )
    invoice_date: date = Field(
        ...,
        description="Date the invoice was issued",
    )
    vendor_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Legal entity or business name issuing the invoice",
    )
    currency: Annotated[
        str,
        Field(
            min_length=1,
            max_length=10,
            description="Currency code (e.g. USD, EUR, GBP) or recognized symbol",
        ),
    ]
    subtotal: Decimal | None = Field(
        default=None,
        ge=0,
        description="Net amount before tax and additional charges",
    )
    tax: Decimal | None = Field(
        default=None,
        ge=0,
        description="Tax or VAT amount",
    )
    total: Decimal = Field(
        ...,
        ge=0,
        description="Gross total payable amount including tax",
    )


class InvoiceExtractionRecord(BaseModel):
    """Full container for an invoice extraction event including metadata, data, and evidence."""

    document_id: str = Field(
        ..., description="Unique internal identifier for the processed document"
    )
    file_name: str = Field(..., description="Original filename of the ingested document")
    data: InvoiceData | None = Field(
        default=None, description="Extracted invoice data if parse succeeded"
    )
    evidence: dict[str, FieldEvidence] = Field(
        default_factory=dict,
        description="Mapping of field names to their grounding evidence",
    )
    validation_passed: bool = Field(
        default=False,
        description="Whether data passed both schema and business rule validations",
    )
    review_status: str = Field(
        default="pending",
        description="Review state: pending, approved, rejected, corrected",
    )
