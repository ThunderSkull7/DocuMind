"""Invoice document schemas and evidence models for DocuMind.

Defines structured representation of invoice fields, line items, evidence provenance,
and extraction records.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractionMethod(str, Enum):
    """Extraction mechanism utilized for retrieving a value."""

    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    RULE_BASED = "rule_based"
    PATTERN = "pattern"
    SPATIAL = "spatial"
    KEYWORD = "keyword"
    HUMAN_CORRECTION = "human_correction"


class EvidenceStatus(str, Enum):
    """Extraction status and reliability of an evidence item."""

    EXTRACTED = "extracted"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    NEEDS_REVIEW = "needs_review"


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
    field_name: str | None = Field(
        default=None, description="Canonical field name associated with this evidence"
    )
    extracted_value: Any = Field(
        default=None, description="Normalized value derived from this evidence"
    )
    source_method: str | None = Field(
        default=None, description="Underlying page extraction method: native_text or ocr"
    )
    ocr_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Original OCR engine confidence for constituent words if OCR",
    )
    status: EvidenceStatus = Field(
        default=EvidenceStatus.EXTRACTED,
        description="Completeness/certainty status of extracted field evidence",
    )
    candidates: list[Any] = Field(
        default_factory=list,
        description="Alternative candidate values or interpretations when ambiguous",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Extraction or interpretation warnings for this field",
    )


class ExtractedField(BaseModel):
    """Generic wrapper for an extracted field value paired with its grounding evidence."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: str | Decimal | date | None = None
    evidence: FieldEvidence | None = None
    is_valid: bool = True
    error_message: str | None = None


class InvoiceLineItem(BaseModel):
    """Structured line item extracted from invoice table rows."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(..., min_length=1, description="Item or service description")
    quantity: Decimal | None = Field(default=None, description="Billed quantity or hours")
    unit_of_measure: str | None = Field(default=None, description="Unit of measure if explicit")
    unit_price: Decimal | None = Field(default=None, description="Rate or unit price")
    discount: Decimal | None = Field(default=None, description="Line item discount if present")
    tax: Decimal | None = Field(default=None, description="Line item tax if present")
    total: Decimal | None = Field(default=None, description="Extended line item total amount")
    raw_text: str | None = Field(default=None, description="Full raw text of line item row")
    bounding_box: BoundingBox | None = Field(
        default=None, description="Spatial bounding box spanning the row"
    )
    page_number: int | None = Field(
        default=None, ge=1, description="Page number where line item was located"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence of line item extraction"
    )
    status: str = Field(
        default="extracted", description="Extraction status (extracted, ambiguous, needs_review)"
    )


class InvoiceData(BaseModel):
    """Structured invoice fields extracted from a document."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Core required invoice identification
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
    total: Decimal = Field(
        ...,
        ge=0,
        description="Gross total payable amount including tax",
    )

    # Core optional financial fields
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

    # Extended invoice identification
    due_date: date | None = Field(
        default=None,
        description="Date payment is due",
    )
    purchase_order_number: str | None = Field(
        default=None,
        max_length=100,
        description="Client purchase order number reference",
    )

    # Extended vendor information
    vendor_address: str | None = Field(
        default=None,
        max_length=500,
        description="Physical or registered corporate address of the vendor",
    )
    vendor_email: str | None = Field(
        default=None,
        max_length=200,
        description="Contact email address for vendor billing",
    )
    vendor_phone: str | None = Field(
        default=None,
        max_length=100,
        description="Contact phone number for the vendor",
    )
    vendor_tax_id: str | None = Field(
        default=None,
        max_length=100,
        description="Tax, VAT, or corporate identifier for the vendor",
    )

    # Extended customer information
    customer_name: str | None = Field(
        default=None,
        max_length=200,
        description="Customer, client, or bill-to organization name",
    )
    customer_address: str | None = Field(
        default=None,
        max_length=500,
        description="Billing or delivery address of the customer",
    )
    customer_email: str | None = Field(
        default=None,
        max_length=200,
        description="Customer contact email if specified",
    )
    customer_tax_id: str | None = Field(
        default=None,
        max_length=100,
        description="Tax or VAT identifier of customer",
    )

    # Extended financial summary
    tax_rate: Decimal | None = Field(
        default=None,
        ge=0,
        description="Explicit tax rate percentage applied (e.g. 0.10 for 10%)",
    )
    discount_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Discounts applied to invoice total",
    )
    shipping_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Freight, shipping, or dispatch fees",
    )
    amount_paid: Decimal | None = Field(
        default=None,
        ge=0,
        description="Amount already paid prior to invoice issuance",
    )
    balance_due: Decimal | None = Field(
        default=None,
        ge=0,
        description="Outstanding balance payable",
    )

    # Line items
    line_items: list[InvoiceLineItem] = Field(
        default_factory=list,
        description="Extracted table line items",
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
    raw_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of raw extracted values prior to or during validation",
    )
    evidence: dict[str, FieldEvidence] = Field(
        default_factory=dict,
        description="Mapping of field names to their grounding evidence",
    )
    validation_passed: bool = Field(
        default=False,
        description="Whether data passed both schema and business rule validations",
    )
    validation_errors: list[str] = Field(
        default_factory=list,
        description="List of validation errors if schema validation failed",
    )
    review_status: str = Field(
        default="pending",
        description="Review state: pending, approved, rejected, corrected, needs_review",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Document-level extraction and interpretation warnings",
    )
