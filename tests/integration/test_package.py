"""Integration tests verifying package imports and core wiring."""

import pytest


@pytest.mark.integration
def test_package_and_submodules_import() -> None:
    """Verify all first-party DocuMind modules can be imported without errors."""
    import documind
    import documind.config
    import documind.exceptions
    import documind.extraction
    import documind.ingestion
    import documind.logging
    import documind.matching
    import documind.reporting
    import documind.review
    import documind.schemas
    import documind.validation

    assert documind.__version__ == "0.1.0"


@pytest.mark.integration
def test_external_dependencies_import() -> None:
    """Verify that expected third-party dependencies are available."""
    import pydantic
    import pymupdf
    import pytesseract
    import streamlit

    assert pymupdf.__doc__ is not None
    assert pydantic.__version__ is not None
    assert pytesseract.__file__ is not None
    assert streamlit.__version__ is not None


@pytest.mark.integration
def test_logging_setup() -> None:
    """Verify that documind logging can be initialized cleanly."""
    import io

    from documind.logging import configure_logging, get_logger

    stream = io.StringIO()
    configure_logging(level="DEBUG", stream=stream)
    scoped_logger = get_logger("test_module")

    scoped_logger.info("Test log message")
    output = stream.getvalue()
    assert "Test log message" in output
    assert "INFO" in output
