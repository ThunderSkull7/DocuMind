"""Unit tests verifying PDF page rasterization and spatial evidence bounding-box highlights."""

from pathlib import Path

from app.components.pdf_viewer import render_pdf_page

from documind.schemas.invoice import BoundingBox


def test_render_pdf_page_valid() -> None:
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    assert pdf_path.is_file()

    img, meta = render_pdf_page(pdf_path, page_number=1, dpi=100)
    assert img is not None
    assert meta["success"] is True
    assert meta["total_pages"] >= 1
    assert meta["page_number"] == 1
    assert meta["rendered_width_px"] > 0
    assert meta["rendered_height_px"] > 0
    assert meta["highlight_applied"] is False


def test_render_pdf_page_with_highlight() -> None:
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    box = BoundingBox(page=1, x0=100.0, y0=150.0, x1=250.0, y1=170.0)

    img, meta = render_pdf_page(pdf_path, page_number=1, highlight_box=box, dpi=100)
    assert img is not None
    assert meta["success"] is True
    assert meta["highlight_applied"] is True
    assert "highlight_pixel_box" in meta
    px_box = meta["highlight_pixel_box"]
    assert len(px_box) == 4
    assert px_box[2] > px_box[0]


def test_render_pdf_page_out_of_bounds() -> None:
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    img, meta = render_pdf_page(pdf_path, page_number=999)
    assert img is None
    assert meta["success"] is False
    assert "out of bounds" in meta["error"]


def test_render_pdf_page_invalid_path() -> None:
    img, meta = render_pdf_page(Path("nonexistent_invoice.pdf"), page_number=1)
    assert img is None
    assert meta["success"] is False
    assert meta["error"] is not None
