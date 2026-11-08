"""DocuMind Streamlit Application - Entry Point.

Phase 1 skeleton providing system diagnostic status, architecture overview,
and readiness verification.
"""

import sys

import streamlit as st

from documind import __version__
from documind.config import get_settings


def main() -> None:
    st.set_page_config(
        page_title="DocuMind - Document Extraction & Verification",
        page_icon="📄",
        layout="wide",
    )

    settings = get_settings()

    st.title("📄 DocuMind")
    st.subheader("Intelligent Document Extraction & Verification System")

    st.info(
        f"**Phase 1 Foundation Active** — Version {__version__} | Environment: `{settings.env}`"
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 🏛️ System Architecture & Processing Pipeline")
        st.markdown(
            """
            DocuMind is structured into clear modular components for invoice processing:

            1. **Ingestion**: File validation (MIME, size, PDF integrity) and secure isolated storage.
            2. **Extraction**: Native PDF text extraction (PyMuPDF) with OCR fallback (Tesseract).
            3. **Schemas**: Pydantic models with confidence scoring and spatial bounding box evidence.
            4. **Validation**: Two-tier schema validation and arithmetic business rules (`subtotal + tax = total`).
            5. **Matching**: Reference-record matching for vendor and PO reconciliation.
            6. **Review**: Human-in-the-loop review interface with complete audit trail.
            7. **Reporting**: Structured export to CSV and JSON formats.
            """
        )

        st.markdown("### 📋 Pipeline Flow")
        st.code(
            "Upload ➔ File Validation ➔ Safe Storage ➔ Native PDF Text Extraction\n"
            "➔ OCR Fallback ➔ Text Normalization ➔ Structured Extraction\n"
            "➔ Schema Validation ➔ Business Validation ➔ Evidence Generation\n"
            "➔ Human Review ➔ Approval ➔ Export",
            language="text",
        )

    with col2:
        st.markdown("### ⚙️ Environment & Diagnostics")
        st.write(f"**Python Version:** `{sys.version.split()[0]}`")
        st.write(f"**Log Level:** `{settings.log_level}`")
        st.write(f"**Max Upload Size:** `{settings.max_upload_size_mb} MB`")
        st.write(f"**Allowed MIME Types:** `{', '.join(settings.allowed_mime_types)}`")
        st.write(f"**Project Root:** `{settings.project_root.name}`")
        st.write(
            f"**Tesseract Path:** `{'Configured' if settings.tesseract_cmd else 'System PATH'}`"
        )

        st.success("✅ Foundation modules initialized and ready for Phase 2.")


if __name__ == "__main__":
    main()
