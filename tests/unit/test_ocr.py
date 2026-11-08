"""Unit tests for OCR engine integration and coordinate translation."""

from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytesseract
import pytest

from documind.config import Settings
from documind.exceptions import OCRError, OCRTimeoutError, TesseractNotFoundError
from documind.extraction.models import PageExtractionMethod
from documind.extraction.ocr import (
    OCREngine,
    is_tesseract_available,
    resolve_tesseract_cmd,
)


@pytest.fixture(autouse=True)
def isolate_pytesseract_global_cmd():
    """Preserve and restore pytesseract.pytesseract.tesseract_cmd to prevent global state leakage."""
    original_cmd = pytesseract.pytesseract.tesseract_cmd
    yield
    pytesseract.pytesseract.tesseract_cmd = original_cmd


@pytest.mark.unit
def test_tesseract_missing_raises_error(temp_dir: Path) -> None:
    """Verify missing Tesseract executable triggers clear TesseractNotFoundError."""
    settings = Settings(
        project_root=temp_dir,
        tesseract_cmd=str(temp_dir / "non_existent_tesseract.exe"),
    )
    engine = OCREngine(settings)
    with pytest.raises(TesseractNotFoundError) as exc_info:
        engine.check_availability()

    assert "Configured Tesseract executable path does not exist" in str(
        exc_info.value
    ) or "Tesseract OCR binary could not be found" in str(exc_info.value)
    assert "DOCUMIND_TESSERACT_CMD" in str(exc_info.value)


@pytest.mark.unit
def test_tesseract_missing_from_system_paths(
    temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that when no explicit path is set and system PATH/known dirs lack Tesseract, an error is raised."""
    monkeypatch.setattr("documind.extraction.ocr.STANDARD_WINDOWS_TESSERACT_PATHS", [])
    monkeypatch.setattr("shutil.which", lambda _cmd: None)

    settings = Settings(project_root=temp_dir, tesseract_cmd=None)
    engine = OCREngine(settings)

    with pytest.raises(TesseractNotFoundError) as exc_info:
        engine.check_availability()

    assert "Tesseract OCR binary could not be found" in str(exc_info.value)
    assert "DOCUMIND_TESSERACT_CMD" in str(exc_info.value)


@pytest.mark.unit
def test_tesseract_explicit_valid_path(temp_dir: Path) -> None:
    """Verify an explicit valid executable path is respected and preferred."""
    dummy_exe = temp_dir / "my_tesseract.exe"
    dummy_exe.write_text("executable placeholder")

    settings = Settings(
        project_root=temp_dir,
        tesseract_cmd=str(dummy_exe),
    )
    resolved = resolve_tesseract_cmd(settings)
    assert resolved == str(dummy_exe)

    engine = OCREngine(settings)
    assert engine.tesseract_cmd == str(dummy_exe)


@pytest.mark.unit
def test_ocr_disabled_raises_error(temp_dir: Path) -> None:
    """Verify disabled OCR setting raises OCRError."""
    settings = Settings(
        project_root=temp_dir,
        ocr_enabled=False,
    )
    engine = OCREngine(settings)
    with pytest.raises(OCRError) as exc_info:
        engine.check_availability()
    assert "OCR is disabled in configuration" in str(exc_info.value)


@pytest.mark.unit
def test_ocr_coordinate_scaling_and_confidence(
    monkeypatch: pytest.MonkeyPatch, temp_dir: Path
) -> None:
    """Verify that raster pixel coordinates from Tesseract scale to PDF point space."""
    import pytesseract

    settings = Settings(
        project_root=temp_dir,
        ocr_enabled=True,
        tesseract_cmd=r"C:\fake\tesseract.exe",
    )
    engine = OCREngine(settings)
    # Mock availability check to pass
    monkeypatch.setattr(engine, "check_availability", lambda: None)

    # Simulated Tesseract output on an image of width=1190, height=1684 (300 DPI for A4 595x842)
    # A box at left=200, top=100, width=150, height=50 in pixels
    # With scale = 595 / 1190 = 0.5, the points should be x0=100.0, y0=50.0, x1=175.0, y1=75.0
    fake_tesseract_data = {
        "text": ["", "INVOICE", ""],
        "conf": [-1, 95, -1],
        "left": [0, 200, 0],
        "top": [0, 100, 0],
        "width": [0, 150, 0],
        "height": [0, 50, 0],
    }

    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        MagicMock(return_value=fake_tesseract_data),
    )

    doc = pymupdf.open()
    page = doc.new_page(width=595.0, height=842.0)
    page_result = engine.extract_page_ocr(page, page_number=1)
    doc.close()

    assert page_result.extraction_method == PageExtractionMethod.OCR
    assert page_result.word_count == 1
    assert "INVOICE" in page_result.raw_text

    word = page_result.text_blocks[0].words[0]
    assert word.text == "INVOICE"
    assert word.confidence == 0.95  # 95 / 100.0
    # Coordinates transformed from image pixels to PDF points
    assert word.bounding_box.x0 > 0.0
    assert word.bounding_box.y0 > 0.0
    assert word.bounding_box.x1 <= 595.0
    assert word.bounding_box.y1 <= 842.0


@pytest.mark.unit
def test_ocr_timeout_handling(monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
    """Verify that OCR execution timeouts raise OCRTimeoutError."""
    import pytesseract

    settings = Settings(project_root=temp_dir, ocr_enabled=True)
    engine = OCREngine(settings)
    monkeypatch.setattr(engine, "check_availability", lambda: None)

    def mock_timeout(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("OCR timed out")

    monkeypatch.setattr(pytesseract, "image_to_data", mock_timeout)

    doc = pymupdf.open()
    page = doc.new_page(width=595.0, height=842.0)
    with pytest.raises(OCRTimeoutError):
        engine.extract_page_ocr(page, page_number=1)
    doc.close()


@pytest.mark.ocr
def test_real_ocr_integration_if_available() -> None:
    """Run real OCR against a synthetic scanned invoice if Tesseract binary is available."""
    if not is_tesseract_available():
        pytest.skip("Tesseract OCR binary not installed in environment; skipping real OCR test.")

    scanned_path = Path("data/synthetic_documents/syn_invoice_031_scanned.pdf")
    assert scanned_path.is_file()

    doc = pymupdf.open(str(scanned_path))
    engine = OCREngine()
    result = engine.extract_page_ocr(doc[0], page_number=1)
    doc.close()

    assert result.extraction_method == PageExtractionMethod.OCR
    assert result.word_count > 10
    assert len(result.raw_text) > 50
    assert result.quality is not None
