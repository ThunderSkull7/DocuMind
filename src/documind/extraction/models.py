"""Pydantic models for structured document extraction output and spatial evidence.

Defines standardized containers for page-aware extraction, spatial blocks,
word tokens with coordinates, quality signals, and top-level results.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from documind.schemas.invoice import BoundingBox


class ExtractionStatus(str, Enum):
    """Execution status of document extraction."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class PageExtractionMethod(str, Enum):
    """Mechanism utilized for extracting an individual document page."""

    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    FAILED = "failed"


class OverallExtractionMethod(str, Enum):
    """Summary of extraction strategies across all pages in a document."""

    NATIVE_ONLY = "native_only"
    OCR_ONLY = "ocr_only"
    HYBRID = "hybrid"
    FAILED = "failed"


class SpatialWord(BaseModel):
    """Word-level token with spatial bounding box and provenance.

    Coordinates use PDF point units with the origin (0, 0) at the top-left corner.
    Confidence is explicitly None for native PDF extraction and represents engine-reported
    confidence for OCR recognition.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., description="Extracted word text")
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    bounding_box: BoundingBox = Field(
        ..., description="Spatial box in PDF points (top-left origin)"
    )
    reading_order_index: int = Field(
        ..., ge=0, description="Sequential token position in reading flow"
    )
    extraction_method: PageExtractionMethod = Field(..., description="Extraction engine used")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Engine-reported recognition confidence (None for native PDF extraction)",
    )


class SpatialTextBlock(BaseModel):
    """Coherent paragraph, heading, or table cell block containing constituent words."""

    model_config = ConfigDict(extra="forbid")

    block_index: int = Field(..., ge=0, description="0-indexed block sequence on page")
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    bounding_box: BoundingBox = Field(..., description="Spatial bounding box for entire block")
    text: str = Field(..., description="Raw text of block with natural line breaks")
    words: list[SpatialWord] = Field(default_factory=list, description="Constituent spatial words")
    extraction_method: PageExtractionMethod = Field(..., description="Extraction engine used")


class ExtractionQuality(BaseModel):
    """Quality indicators assessed for a page's text representation."""

    model_config = ConfigDict(extra="forbid")

    character_count: int = Field(..., ge=0, description="Total characters extracted")
    word_count: int = Field(..., ge=0, description="Total whitespace-delimited words")
    alphanumeric_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Ratio of alphanumeric characters"
    )
    text_density: float = Field(..., ge=0.0, description="Characters per 1,000 square PDF points")
    replacement_char_count: int = Field(
        default=0, ge=0, description="Count of Unicode replacement characters"
    )
    is_sufficient_for_native: bool = Field(
        ..., description="True if text meets native routing thresholds"
    )
    signals: dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic signals")


class PageExtraction(BaseModel):
    """Extracted text, spatial elements, and metadata for a single document page."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    extraction_method: PageExtractionMethod = Field(..., description="Method used for this page")
    raw_text: str = Field(..., description="Unaltered raw extracted text stream")
    normalized_text: str = Field(
        ..., description="Normalized text stream preserving semantic values"
    )
    text_blocks: list[SpatialTextBlock] = Field(default_factory=list, description="Spatial blocks")
    word_count: int = Field(default=0, ge=0, description="Count of words on page")
    character_count: int = Field(default=0, ge=0, description="Count of characters on page")
    page_width: float = Field(..., gt=0, description="Page width in PDF points")
    page_height: float = Field(..., gt=0, description="Page height in PDF points")
    quality: ExtractionQuality | None = Field(
        default=None, description="Quality assessment details"
    )
    warnings: list[str] = Field(default_factory=list, description="Non-fatal page warnings")
    error: str | None = Field(default=None, description="Error message if page extraction failed")


class RoutingDecision(BaseModel):
    """Page-level routing choice and rationale."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    selected_method: PageExtractionMethod = Field(..., description="Chosen extraction method")
    reason: str = Field(..., description="Human-readable justification for the routing choice")
    native_quality: ExtractionQuality = Field(
        ..., description="Signals evaluated during native check"
    )
    ocr_attempted: bool = Field(default=False, description="Whether OCR was executed")
    fallback_triggered: bool = Field(
        default=False, description="Whether fallback from native occurred"
    )


class ExtractionResult(BaseModel):
    """Comprehensive, standardized extraction output for an ingested document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., description="Internal document identifier")
    source_file_hash: str = Field(
        ..., min_length=64, max_length=64, description="SHA-256 hash of source PDF"
    )
    extraction_status: ExtractionStatus = Field(
        ..., description="Overall document extraction outcome"
    )
    overall_extraction_method: OverallExtractionMethod = Field(
        ..., description="Summary strategy used"
    )
    pages: list[PageExtraction] = Field(..., description="Extracted pages in reading order")
    total_pages: int = Field(..., ge=0, description="Total pages in document")
    processing_duration_ms: float = Field(
        ..., ge=0.0, description="Execution duration in milliseconds"
    )
    warnings: list[str] = Field(default_factory=list, description="Document-level warnings")
    errors: list[str] = Field(default_factory=list, description="Document-level errors")
    engine_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Runtime engine configurations"
    )
