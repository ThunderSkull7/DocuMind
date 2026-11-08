"""Extraction orchestration service coordinating document retrieval, routing, and output synthesis."""

import hashlib
import time
from typing import BinaryIO

import pymupdf

from documind import __version__
from documind.config import Settings, get_settings
from documind.extraction.models import (
    ExtractionResult,
    ExtractionStatus,
    OverallExtractionMethod,
    PageExtraction,
    PageExtractionMethod,
)
from documind.extraction.ocr import OCREngine, is_tesseract_available, resolve_tesseract_cmd
from documind.extraction.routing import PageExtractionRouter
from documind.ingestion.service import IngestionService
from documind.ingestion.storage import StorageManager
from documind.logging import get_logger

logger = get_logger("extraction.service")


class ExtractionService:
    """Orchestrates hybrid document extraction across ingested records."""

    def __init__(
        self,
        settings: Settings | None = None,
        storage_manager: StorageManager | None = None,
        ingestion_service: IngestionService | None = None,
        ocr_engine: OCREngine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage_manager or StorageManager(self.settings)
        self.ingestion = ingestion_service or IngestionService(self.settings, self.storage)
        self.ocr_engine = ocr_engine or OCREngine(self.settings)
        self.router = PageExtractionRouter(self.settings, self.ocr_engine)

    def extract_document(
        self,
        document_id: str,
        expected_hash: str | None = None,
    ) -> ExtractionResult:
        """Extract text and spatial layouts for an ingested document by its document ID.

        Args:
            document_id: UUIDv4 identifier of the ingested document.
            expected_hash: Optional SHA-256 digest to verify document integrity.

        Returns:
            ExtractionResult containing structured page-level text and spatial models.
        """
        start_time = time.perf_counter()
        warnings: list[str] = []

        # 1. Retrieve stored file
        file_path = self.storage.retrieve(document_id)
        if not file_path or not file_path.is_file():
            err_msg = f"Document '{document_id}' not found in storage."
            logger.error(err_msg)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExtractionResult(
                document_id=document_id,
                source_file_hash="0" * 64,
                extraction_status=ExtractionStatus.FAILED,
                overall_extraction_method=OverallExtractionMethod.FAILED,
                pages=[],
                total_pages=0,
                processing_duration_ms=round(duration_ms, 2),
                warnings=warnings,
                errors=[err_msg],
                engine_metadata=self._get_engine_metadata(),
            )

        # 2. Verify SHA-256 hash integrity
        content_bytes = file_path.read_bytes()
        actual_hash = hashlib.sha256(content_bytes).hexdigest()

        if expected_hash and actual_hash != expected_hash:
            err_msg = (
                f"Document integrity verification failed for {document_id}. "
                f"Expected {expected_hash[:16]}... but found {actual_hash[:16]}..."
            )
            logger.error(err_msg)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExtractionResult(
                document_id=document_id,
                source_file_hash=actual_hash,
                extraction_status=ExtractionStatus.FAILED,
                overall_extraction_method=OverallExtractionMethod.FAILED,
                pages=[],
                total_pages=0,
                processing_duration_ms=round(duration_ms, 2),
                warnings=warnings,
                errors=[err_msg],
                engine_metadata=self._get_engine_metadata(),
            )

        return self.extract_from_bytes(
            content=content_bytes,
            document_id=document_id,
            source_file_hash=actual_hash,
            start_time=start_time,
        )

    def extract_from_bytes(
        self,
        content: bytes | BinaryIO,
        document_id: str = "adhoc-document",
        source_file_hash: str | None = None,
        start_time: float | None = None,
    ) -> ExtractionResult:
        """Extract text and spatial layouts directly from raw bytes or stream.

        Args:
            content: Raw PDF bytes or file-like stream.
            document_id: Identifier label.
            source_file_hash: Precomputed SHA-256 hash or computed from bytes.
            start_time: Optional timer start point.

        Returns:
            ExtractionResult with page extractions and routing metadata.
        """
        t0 = start_time or time.perf_counter()
        warnings: list[str] = []
        errors: list[str] = []

        if isinstance(content, bytes):
            raw_bytes = content
        else:
            raw_bytes = content.read()

        file_hash = source_file_hash or hashlib.sha256(raw_bytes).hexdigest()

        # 3. Open PDF safely
        try:
            doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
        except Exception as exc:
            err_msg = f"Failed to parse PDF document for extraction: {exc}"
            logger.error(err_msg)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return ExtractionResult(
                document_id=document_id,
                source_file_hash=file_hash,
                extraction_status=ExtractionStatus.FAILED,
                overall_extraction_method=OverallExtractionMethod.FAILED,
                pages=[],
                total_pages=0,
                processing_duration_ms=round(duration_ms, 2),
                warnings=warnings,
                errors=[err_msg],
                engine_metadata=self._get_engine_metadata(),
            )

        extracted_pages: list[PageExtraction] = []
        page_methods_used: set[PageExtractionMethod] = set()

        try:
            total_pages = len(doc)
            for idx in range(total_pages):
                page_num = idx + 1
                page = doc[idx]

                try:
                    page_extraction, decision = self.router.route_and_extract_page(
                        page=page,
                        page_number=page_num,
                    )
                    extracted_pages.append(page_extraction)
                    page_methods_used.add(page_extraction.extraction_method)

                    if page_extraction.warnings:
                        warnings.extend(f"Page {page_num}: {w}" for w in page_extraction.warnings)

                except Exception as page_exc:
                    err_page = f"Page {page_num} extraction failed: {page_exc}"
                    logger.error(err_page)
                    errors.append(err_page)

                    failed_page = PageExtraction(
                        page_number=page_num,
                        extraction_method=PageExtractionMethod.FAILED,
                        raw_text="",
                        normalized_text="",
                        text_blocks=[],
                        word_count=0,
                        character_count=0,
                        page_width=float(page.rect.width),
                        page_height=float(page.rect.height),
                        quality=None,
                        warnings=[],
                        error=str(page_exc),
                    )
                    extracted_pages.append(failed_page)
                    page_methods_used.add(PageExtractionMethod.FAILED)

        finally:
            doc.close()

        # 4. Determine overall extraction method
        if (
            PageExtractionMethod.NATIVE_TEXT in page_methods_used
            and PageExtractionMethod.OCR in page_methods_used
        ):
            overall_method = OverallExtractionMethod.HYBRID
        elif PageExtractionMethod.OCR in page_methods_used:
            overall_method = OverallExtractionMethod.OCR_ONLY
        elif PageExtractionMethod.NATIVE_TEXT in page_methods_used:
            overall_method = OverallExtractionMethod.NATIVE_ONLY
        else:
            overall_method = OverallExtractionMethod.FAILED

        # 5. Determine overall extraction status
        has_failed_pages = PageExtractionMethod.FAILED in page_methods_used
        has_success_pages = (
            PageExtractionMethod.NATIVE_TEXT in page_methods_used
            or PageExtractionMethod.OCR in page_methods_used
        )

        if has_failed_pages and has_success_pages:
            status = ExtractionStatus.PARTIAL_SUCCESS
        elif has_failed_pages or not extracted_pages:
            status = ExtractionStatus.FAILED
        else:
            status = ExtractionStatus.SUCCESS

        duration_ms = (time.perf_counter() - t0) * 1000.0

        return ExtractionResult(
            document_id=document_id,
            source_file_hash=file_hash,
            extraction_status=status,
            overall_extraction_method=overall_method,
            pages=extracted_pages,
            total_pages=len(extracted_pages),
            processing_duration_ms=round(duration_ms, 2),
            warnings=warnings,
            errors=errors,
            engine_metadata=self._get_engine_metadata(),
        )

    def _get_engine_metadata(self) -> dict:
        """Capture runtime engine metadata for provenance tracking."""
        return {
            "documind_version": __version__,
            "pymupdf_version": pymupdf.__version__,
            "tesseract_available": is_tesseract_available(self.settings),
            "tesseract_cmd": resolve_tesseract_cmd(self.settings),
            "ocr_enabled": self.settings.ocr_enabled,
            "ocr_dpi": self.settings.ocr_dpi,
            "ocr_psm": self.settings.ocr_psm,
            "routing_min_char_count": self.settings.routing_min_char_count,
            "routing_min_alpha_ratio": self.settings.routing_min_alpha_ratio,
            "routing_min_word_count": self.settings.routing_min_word_count,
        }
