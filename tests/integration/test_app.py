"""Integration test verifying that the Streamlit entry point executes cleanly."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.integration
def test_streamlit_home_page_renders() -> None:
    """Verify app/Home.py executes without raising unhandled exceptions."""
    project_root = Path(__file__).resolve().parents[2]
    app_entry = project_root / "app" / "Home.py"
    app = AppTest.from_file(str(app_entry))
    app.run()
    assert not app.exception
    assert len(app.title) >= 1
    assert "DocuMind" in app.title[0].value
