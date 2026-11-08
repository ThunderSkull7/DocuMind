"""Pytest configuration and common fixtures for DocuMind test suite."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from documind.config import Settings


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test file operations."""
    with tempfile.TemporaryDirectory() as tmp_path:
        yield Path(tmp_path)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Provide a test Settings instance isolated in a temporary directory."""
    return Settings(
        env="test",
        log_level="DEBUG",
        project_root=temp_dir,
        DOCUMIND_DATA_DIR="test_data",
        DOCUMIND_STORAGE_DIR="test_storage",
        DOCUMIND_REPORTS_DIR="test_reports",
    )
