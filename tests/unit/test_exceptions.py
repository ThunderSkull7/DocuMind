"""Unit tests for DocuMind exception hierarchy."""

import pytest

from documind.exceptions import (
    DocuMindError,
    ExtractionError,
    IngestionError,
    OCRError,
    SchemaValidationError,
    UnsupportedFileTypeError,
    ValidationError,
)


@pytest.mark.unit
def test_exception_inheritance() -> None:
    """Verify that domain exceptions inherit properly from DocuMindError."""
    assert issubclass(IngestionError, DocuMindError)
    assert issubclass(UnsupportedFileTypeError, IngestionError)
    assert issubclass(ExtractionError, DocuMindError)
    assert issubclass(OCRError, ExtractionError)
    assert issubclass(ValidationError, DocuMindError)
    assert issubclass(SchemaValidationError, ValidationError)


@pytest.mark.unit
def test_exception_formatting() -> None:
    """Verify exception string representation with and without details."""
    err_simple = DocuMindError("Simple error")
    assert str(err_simple) == "Simple error"

    err_detailed = DocuMindError("Detailed error", details={"field": "total", "code": 400})
    assert "field" in str(err_detailed)
    assert "total" in str(err_detailed)
