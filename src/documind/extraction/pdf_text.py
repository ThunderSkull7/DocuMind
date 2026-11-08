"""Native PDF text extraction engine using PyMuPDF.

Extracts text, spatial blocks, word tokens with bounding boxes,
and page dimensions while preserving reading order.
"""

from collections import defaultdict
from pathlib import Path
from typing import BinaryIO

import pymupdf

from documind.config import Settings, get_settings
from documind.exceptions import PDFExtractionError
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

logger = get_logger("extraction.pdf_text")


def extract_native_page(
    page: pymupdf.Page,
    page_number: int,
    settings: Settings | None = None,
) -> PageExtraction:
    """Extract native text and spatial layout elements from a single PyMuPDF page.

    Args:
        page: PyMuPDF Page instance.
        page_number: 1-indexed page sequence number.
        settings: Application settings.

    Returns:
        PageExtraction container with raw/normalized text, blocks, and words.
    """
    rect = page.rect
    page_width = float(rect.width)
    page_height = float(rect.height)

    raw_text = page.get_text("text") or ""
    normalized = normalize_text(raw_text)

    # Extract words: (x0, y0, x1, y1, word_str, block_no, line_no, word_no)
    raw_words = page.get_text("words") or []
    spatial_words: list[SpatialWord] = []
    words_by_block: dict[int, list[SpatialWord]] = defaultdict(list)

    for idx, w in enumerate(raw_words):
        x0, y0, x1, y1, word_str, block_no, _, _ = w
        bbox = BoundingBox(
            page=page_number,
            x0=round(float(x0), 2),
            y0=round(float(y0), 2),
            x1=round(float(x1), 2),
            y1=round(float(y1), 2),
        )
        word_token = SpatialWord(
            text=str(word_str),
            page_number=page_number,
            bounding_box=bbox,
            reading_order_index=idx,
            extraction_method=PageExtractionMethod.NATIVE_TEXT,
            confidence=None,  # Native text does not supply statistical confidence
        )
        spatial_words.append(word_token)
        words_by_block[int(block_no)].append(word_token)

    # Extract blocks: (x0, y0, x1, y1, text, block_no, block_type)
    # block_type == 0 indicates text; 1 indicates image
    raw_blocks = page.get_text("blocks") or []
    spatial_blocks: list[SpatialTextBlock] = []

    for b in raw_blocks:
        x0, y0, x1, y1, block_text, block_no, block_type = b
        if block_type == 0:  # Text block only
            block_bbox = BoundingBox(
                page=page_number,
                x0=round(float(x0), 2),
                y0=round(float(y0), 2),
                x1=round(float(x1), 2),
                y1=round(float(y1), 2),
            )
            constituent_words = words_by_block.get(int(block_no), [])
            spatial_blocks.append(
                SpatialTextBlock(
                    block_index=int(block_no),
                    page_number=page_number,
                    bounding_box=block_bbox,
                    text=str(block_text).strip(),
                    words=constituent_words,
                    extraction_method=PageExtractionMethod.NATIVE_TEXT,
                )
            )

    quality = assess_page_quality(
        raw_text=raw_text,
        page_width=page_width,
        page_height=page_height,
        settings=settings,
    )

    return PageExtraction(
        page_number=page_number,
        extraction_method=PageExtractionMethod.NATIVE_TEXT,
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


def extract_native_document(
    doc_input: bytes | Path | str | BinaryIO,
    settings: Settings | None = None,
) -> list[PageExtraction]:
    """Safely open a PDF and extract native text and spatial layout from all pages.

    Args:
        doc_input: PDF bytes, file path, or stream.
        settings: Application settings.

    Returns:
        List of PageExtraction objects, one per document page.

    Raises:
        PDFExtractionError: If document cannot be opened or parsed.
    """
    cfg = settings or get_settings()

    try:
        if isinstance(doc_input, bytes):
            doc = pymupdf.open(stream=doc_input, filetype="pdf")
        elif isinstance(doc_input, (str, Path)):
            doc = pymupdf.open(str(doc_input))
        elif hasattr(doc_input, "read"):
            content = doc_input.read()
            doc = pymupdf.open(stream=content, filetype="pdf")
        else:
            raise PDFExtractionError(f"Unsupported input type: {type(doc_input).__name__}")
    except Exception as exc:
        msg = f"Failed to open PDF document for native extraction: {exc}"
        logger.error(msg)
        raise PDFExtractionError(msg) from exc

    pages: list[PageExtraction] = []
    try:
        for idx, page in enumerate(doc):
            page_num = idx + 1
            extracted_page = extract_native_page(page, page_number=page_num, settings=cfg)
            pages.append(extracted_page)
    except Exception as exc:
        msg = f"Error during native extraction traversal: {exc}"
        logger.error(msg)
        raise PDFExtractionError(msg) from exc
    finally:
        doc.close()

    return pages
