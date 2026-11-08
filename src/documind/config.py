"""Centralized configuration management for DocuMind.

Handles environment variables, default settings, and dynamic path resolution
without hardcoded absolute paths or machine-specific assumptions.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_project_root() -> Path:
    """Derive project root directory relative to this config file."""
    # src/documind/config.py -> parents: 0=documind, 1=src, 2=project root
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """DocuMind application configuration model."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime environment
    env: Literal["development", "staging", "production", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Base path
    project_root: Path = Field(default_factory=get_default_project_root)

    # Directory paths (relative paths resolve against project_root)
    data_dir_name: str = Field(default="data", alias="DOCUMIND_DATA_DIR")
    storage_dir_name: str = Field(default="data/storage", alias="DOCUMIND_STORAGE_DIR")
    reports_dir_name: str = Field(default="reports", alias="DOCUMIND_REPORTS_DIR")

    # Ingestion constraints
    max_upload_size_mb: int = Field(default=25, ge=1, le=100)
    allowed_mime_types: list[str] = Field(default_factory=lambda: ["application/pdf"])
    max_page_count: int = Field(default=50, ge=1, le=1000)
    allow_encrypted_pdfs: bool = Field(default=False)

    # OCR settings
    tesseract_cmd: str | None = None
    ocr_enabled: bool = True
    ocr_default_lang: str = "eng"
    ocr_dpi: int = Field(default=300, ge=72, le=600)
    ocr_psm: int = Field(default=3, ge=0, le=13)
    ocr_timeout_seconds: int = Field(default=30, ge=1, le=300)

    # Hybrid routing thresholds
    routing_min_char_count: int = Field(default=50, ge=0)
    routing_min_alpha_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    routing_min_word_count: int = Field(default=5, ge=0)

    # Streamlit UI settings
    app_host: str = "localhost"
    app_port: int = 8501

    @property
    def data_dir(self) -> Path:
        """Resolved absolute path for the base data directory."""
        path = Path(self.data_dir_name)
        return path if path.is_absolute() else self.project_root / path

    @property
    def storage_dir(self) -> Path:
        """Resolved absolute path for document storage."""
        path = Path(self.storage_dir_name)
        return path if path.is_absolute() else self.project_root / path

    @property
    def reports_dir(self) -> Path:
        """Resolved absolute path for generated reports and exports."""
        path = Path(self.reports_dir_name)
        return path if path.is_absolute() else self.project_root / path

    @property
    def synthetic_data_dir(self) -> Path:
        """Resolved path for synthetic document generation."""
        return self.data_dir / "synthetic_documents"

    @property
    def annotations_dir(self) -> Path:
        """Resolved path for document annotations."""
        return self.data_dir / "annotations"

    def ensure_directories(self) -> None:
        """Create configured runtime directories if they do not exist."""
        for directory in [
            self.data_dir,
            self.storage_dir,
            self.reports_dir,
            self.synthetic_data_dir,
            self.annotations_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
