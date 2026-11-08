"""Extraction module for DocuMind.

Combines high-fidelity native digital PDF text extraction with local Tesseract
OCR fallback, intelligent page-level hybrid routing, spatial coordinate mapping,
deterministic text normalization, and structured invoice field extraction.
"""

from documind.extraction.date_parser import DateParseResult, parse_invoice_date
from documind.extraction.evidence_mapper import EvidenceMapper
from documind.extraction.field_extractor import StructuredInvoiceExtractor
from documind.extraction.line_item_extractor import LineItemExtractor
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
from documind.extraction.money_parser import MoneyParseResult, parse_monetary_value
from documind.extraction.normalization import normalize_text
from documind.extraction.ocr import OCREngine, is_tesseract_available, resolve_tesseract_cmd
from documind.extraction.pdf_text import extract_native_document, extract_native_page
from documind.extraction.quality import assess_page_quality
from documind.extraction.routing import PageExtractionRouter
from documind.extraction.service import ExtractionService
from documind.extraction.spatial import SpatialLine, cluster_words_into_lines
from documind.extraction.vendor_extractor import EntityExtractor

__all__ = [
    "DateParseResult",
    "EntityExtractor",
    "EvidenceMapper",
    "ExtractionQuality",
    "ExtractionResult",
    "ExtractionService",
    "ExtractionStatus",
    "LineItemExtractor",
    "MoneyParseResult",
    "OCREngine",
    "OverallExtractionMethod",
    "PageExtraction",
    "PageExtractionMethod",
    "PageExtractionRouter",
    "RoutingDecision",
    "SpatialLine",
    "SpatialTextBlock",
    "SpatialWord",
    "StructuredInvoiceExtractor",
    "assess_page_quality",
    "cluster_words_into_lines",
    "extract_native_document",
    "extract_native_page",
    "is_tesseract_available",
    "normalize_text",
    "parse_invoice_date",
    "parse_monetary_value",
    "resolve_tesseract_cmd",
]
