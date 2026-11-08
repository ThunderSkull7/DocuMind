"""Page-level hybrid extraction router for DocuMind.

Evaluates native text extraction quality and intelligently triggers OCR fallback
when text density, word count, or character sufficiency falls below thresholds.
"""

import pymupdf

from documind.config import Settings, get_settings
from documind.exceptions import OCRError, TesseractNotFoundError
from documind.extraction.models import (
    PageExtraction,
    PageExtractionMethod,
    RoutingDecision,
)
from documind.extraction.ocr import OCREngine, is_tesseract_available
from documind.extraction.pdf_text import extract_native_page
from documind.logging import get_logger

logger = get_logger("extraction.routing")


class PageExtractionRouter:
    """Evaluates page text signals and routes between native extraction and OCR."""

    def __init__(
        self,
        settings: Settings | None = None,
        ocr_engine: OCREngine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.ocr_engine = ocr_engine or OCREngine(self.settings)

    def route_and_extract_page(
        self,
        page: pymupdf.Page,
        page_number: int,
    ) -> tuple[PageExtraction, RoutingDecision]:
        """Route an individual page to native extraction or OCR fallback.

        Flow:
        1. Attempt native text extraction.
        2. Inspect quality signals (char count, alpha ratio, word count).
        3. If signals meet sufficiency criteria, return native extraction.
        4. If insufficient or empty:
           - If OCR is enabled and Tesseract is available, execute OCR fallback.
           - If OCR is disabled or Tesseract is missing, return native result with warning.

        Args:
            page: PyMuPDF Page instance.
            page_number: 1-indexed page number.

        Returns:
            Tuple of (PageExtraction, RoutingDecision).
        """
        # 1. Attempt native text extraction
        native_page = extract_native_page(page, page_number=page_number, settings=self.settings)
        quality = native_page.quality

        # 2. Check sufficiency
        if quality and quality.is_sufficient_for_native:
            decision = RoutingDecision(
                page_number=page_number,
                selected_method=PageExtractionMethod.NATIVE_TEXT,
                reason=(
                    f"Native text extraction meets quality criteria: "
                    f"{quality.character_count} chars, {quality.word_count} words, "
                    f"alpha ratio {quality.alphanumeric_ratio:.2f}"
                ),
                native_quality=quality,
                ocr_attempted=False,
                fallback_triggered=False,
            )
            return native_page, decision

        # 3. Fallback required: evaluate OCR availability
        tesseract_ready = is_tesseract_available(self.settings)
        ocr_enabled = self.settings.ocr_enabled

        if not ocr_enabled:
            warning_msg = (
                f"Page {page_number} contains insufficient native text ({quality.character_count} chars), "
                f"but OCR is disabled (DOCUMIND_OCR_ENABLED=false)."
            )
            logger.warning(warning_msg)
            native_page.warnings.append(warning_msg)
            decision = RoutingDecision(
                page_number=page_number,
                selected_method=PageExtractionMethod.NATIVE_TEXT,
                reason="Native text insufficient but OCR disabled in settings",
                native_quality=quality,
                ocr_attempted=False,
                fallback_triggered=False,
            )
            return native_page, decision

        if not tesseract_ready:
            warning_msg = (
                f"Page {page_number} appears scanned/image-based ({quality.character_count} chars), "
                f"but Tesseract OCR executable was not found on system PATH."
            )
            logger.warning(warning_msg)
            native_page.warnings.append(warning_msg)
            decision = RoutingDecision(
                page_number=page_number,
                selected_method=PageExtractionMethod.NATIVE_TEXT,
                reason="Native text insufficient but Tesseract OCR binary is unavailable",
                native_quality=quality,
                ocr_attempted=False,
                fallback_triggered=False,
            )
            return native_page, decision

        # 4. Execute OCR Fallback
        try:
            logger.info(
                f"Page {page_number} native text insufficient ({quality.character_count} chars). "
                f"Invoking OCR fallback..."
            )
            ocr_page = self.ocr_engine.extract_page_ocr(page, page_number=page_number)
            decision = RoutingDecision(
                page_number=page_number,
                selected_method=PageExtractionMethod.OCR,
                reason=(
                    f"Native text insufficient ({quality.character_count} chars); "
                    f"OCR extracted {ocr_page.character_count} chars, {ocr_page.word_count} words"
                ),
                native_quality=quality,
                ocr_attempted=True,
                fallback_triggered=True,
            )
            return ocr_page, decision

        except (OCRError, TesseractNotFoundError) as exc:
            err_msg = f"OCR fallback failed on page {page_number}: {exc}"
            logger.error(err_msg)
            native_page.warnings.append(err_msg)
            decision = RoutingDecision(
                page_number=page_number,
                selected_method=PageExtractionMethod.NATIVE_TEXT,
                reason=f"OCR fallback attempted but failed: {exc}",
                native_quality=quality,
                ocr_attempted=True,
                fallback_triggered=True,
            )
            return native_page, decision
