"""Unit tests for DocuMind centralized configuration."""

from pathlib import Path

import pytest

from documind.config import Settings, get_settings


@pytest.mark.unit
def test_default_settings_instantiation() -> None:
    """Verify that settings can be instantiated with default values."""
    settings = get_settings()
    assert settings.env in {"development", "staging", "production", "test"}
    assert settings.max_upload_size_mb == 25
    assert "application/pdf" in settings.allowed_mime_types
    assert settings.project_root.exists()


@pytest.mark.unit
def test_path_resolution(temp_dir: Path) -> None:
    """Verify that relative paths resolve correctly against project_root."""
    settings = Settings(
        project_root=temp_dir,
        DOCUMIND_DATA_DIR="custom_data",
        DOCUMIND_STORAGE_DIR="custom_storage",
    )
    assert settings.data_dir == temp_dir / "custom_data"
    assert settings.storage_dir == temp_dir / "custom_storage"
    assert settings.synthetic_data_dir == temp_dir / "custom_data" / "synthetic_documents"


@pytest.mark.unit
def test_ensure_directories(temp_dir: Path) -> None:
    """Verify that ensure_directories creates required directories."""
    settings = Settings(
        project_root=temp_dir,
        DOCUMIND_DATA_DIR="my_data",
        DOCUMIND_STORAGE_DIR="my_data/storage",
        DOCUMIND_REPORTS_DIR="my_reports",
    )
    assert not settings.data_dir.exists()
    settings.ensure_directories()
    assert settings.data_dir.exists()
    assert settings.storage_dir.exists()
    assert settings.reports_dir.exists()
    assert settings.synthetic_data_dir.exists()


@pytest.mark.unit
def test_env_var_override(monkeypatch: pytest.MonkeyPatch, temp_dir: Path) -> None:
    """Verify environment variable overrides work with DOCUMIND_ prefix."""
    monkeypatch.setenv("DOCUMIND_ENV", "staging")
    monkeypatch.setenv("DOCUMIND_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DOCUMIND_MAX_UPLOAD_SIZE_MB", "50")

    settings = Settings(project_root=temp_dir)
    assert settings.env == "staging"
    assert settings.log_level == "DEBUG"
    assert settings.max_upload_size_mb == 50
