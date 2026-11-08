"""Extraction module for DocuMind.

Combines high-fidelity native digital PDF text extraction with local Tesseract
OCR fallback, intelligent page-level hybrid routing, spatial coordinate mapping,
and deterministic text normalization.
"""

from documind.extraction.models import (
    ExtractionQuality,
    ExtractionResult,
    ExtractionStatus,
    OverallExtractionMethod,
    PageExtraction,
    PageExtractionMethod,
    RoutingDecision,
    SpatialTextBlock,
    SpatialWord,
)
from documind.extraction.normalization import normalize_text
from documind.extraction.ocr import OCREngine, is_tesseract_available, resolve_tesseract_cmd
from documind.extraction.pdf_text import extract_native_document, extract_native_page
from documind.extraction.quality import assess_page_quality
from documind.extraction.routing import PageExtractionRouter
from documind.extraction.service import ExtractionService

__all__ = [
    "ExtractionQuality",
    "ExtractionResult",
    "ExtractionService",
    "ExtractionStatus",
    "OCREngine",
    "OverallExtractionMethod",
    "PageExtraction",
    "PageExtractionMethod",
    "PageExtractionRouter",
    "RoutingDecision",
    "SpatialTextBlock",
    "SpatialWord",
    "assess_page_quality",
    "extract_native_document",
    "extract_native_page",
    "is_tesseract_available",
    "normalize_text",
    "resolve_tesseract_cmd",
]
