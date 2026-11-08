"""PDF viewer component providing page rasterization and spatial evidence highlighting.

Converts PDF point coordinates into rendered pixel coordinates to highlight
constituent words and field tokens with accurate bounding boxes.
"""

import io
from pathlib import Path
from typing import Any

import pymupdf as fitz
from PIL import Image, ImageDraw

from documind.schemas.invoice import BoundingBox


def render_pdf_page(
    pdf_source: Path | bytes,
    page_number: int = 1,
    highlight_box: BoundingBox | None = None,
    dpi: int = 150,
) -> tuple[Image.Image | None, dict[str, Any]]:
    """Render a specified page of a PDF document as a PIL Image with optional evidence highlight.

    Args:
        pdf_source: Filesystem path to the PDF or raw bytes.
        page_number: 1-indexed document page number.
        highlight_box: Optional BoundingBox in PDF point coordinates to highlight.
        dpi: Target rasterization DPI (default 150 for crisp readability).

    Returns:
        Tuple of (PIL Image or None, metadata dictionary).
    """
    metadata: dict[str, Any] = {
        "success": False,
        "total_pages": 0,
        "page_number": page_number,
        "page_width_pt": 0.0,
        "page_height_pt": 0.0,
        "rendered_width_px": 0,
        "rendered_height_px": 0,
        "highlight_applied": False,
        "error": None,
    }

    try:
        if isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            doc = fitz.open(pdf_source)

        metadata["total_pages"] = doc.page_count
        if page_number < 1 or page_number > doc.page_count:
            metadata["error"] = f"Page {page_number} out of bounds (1-{doc.page_count})"
            return None, metadata

        page = doc.load_page(page_number - 1)
        rect = page.rect
        metadata["page_width_pt"] = rect.width
        metadata["page_height_pt"] = rect.height

        # Rasterize to pixmap
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        metadata["rendered_width_px"] = pix.width
        metadata["rendered_height_px"] = pix.height

        # Load into Pillow
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")

        # Apply spatial evidence highlight if requested and valid for this page
        if highlight_box and highlight_box.page == page_number:
            scale_x = pix.width / rect.width
            scale_y = pix.height / rect.height

            # Pad bounding box slightly (+2 pt) for visual breathing room
            x0 = max(0.0, (highlight_box.x0 - 2.0) * scale_x)
            y0 = max(0.0, (highlight_box.y0 - 2.0) * scale_y)
            x1 = min(float(pix.width), (highlight_box.x1 + 2.0) * scale_x)
            y1 = min(float(pix.height), (highlight_box.y1 + 2.0) * scale_y)

            # Draw highlight overlay: amber glow with crisp border
            overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)

            # Translucent fill
            draw.rectangle([x0, y0, x1, y1], fill=(245, 158, 11, 75))
            # Solid boundary outline
            draw.rectangle([x0, y0, x1, y1], outline=(217, 119, 6, 230), width=3)

            img = Image.alpha_composite(img, overlay)
            metadata["highlight_applied"] = True
            metadata["highlight_pixel_box"] = [round(x0), round(y0), round(x1), round(y1)]

        doc.close()
        metadata["success"] = True
        return img.convert("RGB"), metadata

    except Exception as exc:
        metadata["error"] = str(exc)
        return None, metadata
