"""Local OCR engine integration wrapping Tesseract through pytesseract.

Provides page image rasterization via PyMuPDF, word coordinate projection
from raster pixels to PDF point space, engine confidence tracking,
and environment availability verification.
"""

import io
import shutil
from pathlib import Path
from typing import Any

import pymupdf
import pytesseract
from PIL import Image
from pytesseract import Output

from documind.config import Settings, get_settings
from documind.exceptions import OCRError, OCRTimeoutError, TesseractNotFoundError
from documind.extraction.models import (
    PageExtraction,
    PageExtractionMethod,
    SpatialTextBlock,
    SpatialWord,
)
from documind.extraction.normalization import normalize_text
from documind.extraction.quality import assess_page_quality
from documind.logging import get_logger
from documind.schemas.invoice import BoundingBox

logger = get_logger("extraction.ocr")

# Common fallback installation paths on Windows
STANDARD_WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]


def resolve_tesseract_cmd(settings: Settings | None = None) -> str | None:
    """Resolve the executable path for the Tesseract binary.

    Checks:
    1. Explicit setting in DOCUMIND_TESSERACT_CMD.
    2. System PATH via shutil.which('tesseract').
    3. Common Windows default installation paths.

    Returns:
        String path to executable if found, or None.
    """
    cfg = settings or get_settings()

    # 1. Configured path
    if cfg.tesseract_cmd and Path(cfg.tesseract_cmd).is_file():
        return cfg.tesseract_cmd

    # 2. System PATH
    found = shutil.which("tesseract")
    if found:
        return found

    # 3. Known Windows directories
    for win_path in STANDARD_WINDOWS_TESSERACT_PATHS:
        if Path(win_path).is_file():
            return win_path

    return None


def is_tesseract_available(settings: Settings | None = None) -> bool:
    """Return True if Tesseract executable is present and callable."""
    cmd = resolve_tesseract_cmd(settings)
    return cmd is not None


class OCREngine:
    """Wraps Tesseract OCR with coordinate conversion and error diagnostics."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.tesseract_cmd = resolve_tesseract_cmd(self.settings)

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

    def check_availability(self) -> None:
        """Verify Tesseract binary presence; raise TesseractNotFoundError if absent."""
        if not self.settings.ocr_enabled:
            raise OCRError("OCR is disabled in configuration (DOCUMIND_OCR_ENABLED=false).")

        if not self.tesseract_cmd or not is_tesseract_available(self.settings):
            msg = (
                "Tesseract OCR binary could not be found on system PATH or configured path.\n"
                "To resolve on Windows:\n"
                "1. Install Tesseract OCR (e.g. from https://github.com/UB-Mannheim/tesseract/wiki)\n"
                "2. Set DOCUMIND_TESSERACT_CMD in .env to the executable path (e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe)\n"
                "Or add the Tesseract directory to your system PATH."
            )
            logger.error(msg)
            raise TesseractNotFoundError(msg)

    def extract_page_ocr(
        self,
        page: pymupdf.Page,
        page_number: int,
    ) -> PageExtraction:
        """Render a PDF page to raster image and extract text with spatial words via OCR.

        Coordinates from Tesseract (pixel coordinates) are scaled into the PDF
        point coordinate system:
            scale_x = page_width_pts / pixmap_width_px
            scale_y = page_height_pts / pixmap_height_px

        Args:
            page: PyMuPDF Page instance.
            page_number: 1-indexed page number.

        Returns:
            PageExtraction containing recognized words, blocks, and normalized text.
        """
        self.check_availability()

        rect = page.rect
        page_width = float(rect.width)
        page_height = float(rect.height)
        dpi = self.settings.ocr_dpi

        # 1. Rasterize page to pixmap
        try:
            pix = page.get_pixmap(dpi=dpi)
            pix_width = float(pix.width)
            pix_height = float(pix.height)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        except Exception as exc:
            msg = f"Failed to render page {page_number} to image for OCR: {exc}"
            logger.error(msg)
            raise OCRError(msg) from exc

        # Calculate pixel to PDF point scale factors
        scale_x = (page_width / pix_width) if pix_width > 0 else 1.0
        scale_y = (page_height / pix_height) if pix_height > 0 else 1.0

        # Configure Tesseract arguments
        config_args = f"--psm {self.settings.ocr_psm}"
        lang = self.settings.ocr_default_lang
        timeout = self.settings.ocr_timeout_seconds

        # 2. Run Tesseract image_to_data
        try:
            data: dict[str, list[Any]] = pytesseract.image_to_data(
                img,
                lang=lang,
                config=config_args,
                timeout=timeout,
                output_type=Output.DICT,
            )
        except RuntimeError as exc:
            err_lower = str(exc).lower()
            if "timeout" in err_lower or "timed out" in err_lower:
                raise OCRTimeoutError(
                    f"OCR execution timed out after {timeout} seconds on page {page_number}."
                ) from exc
            raise OCRError(f"OCR execution failed on page {page_number}: {exc}") from exc
        except Exception as exc:
            err_lower = str(exc).lower()
            if "timeout" in err_lower or "timed out" in err_lower:
                raise OCRTimeoutError(
                    f"OCR execution timed out after {timeout} seconds on page {page_number}."
                ) from exc
            raise OCRError(f"OCR execution failed on page {page_number}: {exc}") from exc

        # 3. Parse spatial tokens from OCR output
        spatial_words: list[SpatialWord] = []
        raw_words_text: list[str] = []

        # Tesseract data keys: level, page_num, block_num, par_num, line_num, word_num, left, top, width, height, conf, text
        n_boxes = len(data.get("text", []))
        token_idx = 0

        for i in range(n_boxes):
            word_str = str(data["text"][i]).strip()
            if not word_str:
                continue

            raw_conf = float(data["conf"][i]) if "conf" in data else -1.0
            # Tesseract uses -1 for non-word boxes or spaces
            if raw_conf < 0.0:
                engine_conf = 0.0
            else:
                engine_conf = round(min(max(raw_conf / 100.0, 0.0), 1.0), 4)

            left = float(data["left"][i])
            top = float(data["top"][i])
            width = float(data["width"][i])
            height = float(data["height"][i])

            # Transform from image pixels to PDF points
            x0 = round(left * scale_x, 2)
            y0 = round(top * scale_y, 2)
            x1 = round((left + width) * scale_x, 2)
            y1 = round((top + height) * scale_y, 2)

            # Ensure box remains within page bounds
            x0 = max(0.0, min(x0, page_width))
            y0 = max(0.0, min(y0, page_height))
            x1 = max(x0, min(x1, page_width))
            y1 = max(y0, min(y1, page_height))

            bbox = BoundingBox(
                page=page_number,
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
            )

            word_token = SpatialWord(
                text=word_str,
                page_number=page_number,
                bounding_box=bbox,
                reading_order_index=token_idx,
                extraction_method=PageExtractionMethod.OCR,
                confidence=engine_conf,  # Explicit engine-reported confidence
            )
            spatial_words.append(word_token)
            raw_words_text.append(word_str)
            token_idx += 1

        # Reconstruct plain text representation
        raw_text = " ".join(raw_words_text)
        normalized = normalize_text(raw_text)

        # Aggregate spatial words into a page block
        spatial_blocks: list[SpatialTextBlock] = []
        if spatial_words:
            # Overall bounding box covering all recognized words
            min_x0 = min(w.bounding_box.x0 for w in spatial_words)
            min_y0 = min(w.bounding_box.y0 for w in spatial_words)
            max_x1 = max(w.bounding_box.x1 for w in spatial_words)
            max_y1 = max(w.bounding_box.y1 for w in spatial_words)

            block_bbox = BoundingBox(
                page=page_number,
                x0=min_x0,
                y0=min_y0,
                x1=max_x1,
                y1=max_y1,
            )
            spatial_blocks.append(
                SpatialTextBlock(
                    block_index=0,
                    page_number=page_number,
                    bounding_box=block_bbox,
                    text=raw_text,
                    words=spatial_words,
                    extraction_method=PageExtractionMethod.OCR,
                )
            )

        quality = assess_page_quality(
            raw_text=raw_text,
            page_width=page_width,
            page_height=page_height,
            settings=self.settings,
        )

        return PageExtraction(
            page_number=page_number,
            extraction_method=PageExtractionMethod.OCR,
            raw_text=raw_text,
            normalized_text=normalized,
            text_blocks=spatial_blocks,
            word_count=len(spatial_words),
            character_count=len(raw_text),
            page_width=page_width,
            page_height=page_height,
            quality=quality,
            warnings=[],
        )
