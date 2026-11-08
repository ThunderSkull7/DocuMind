"""DocuMind Streamlit Application - Modern Intelligent Document Verification System.

Phase 7 entry point providing system diagnostics, operational health metrics,
and navigation to the multi-page accounts payable review workbench.
"""

import streamlit as st
from app.services.state import get_app_state

from documind import __version__
from documind.config import get_settings
from documind.extraction.ocr import is_tesseract_available, resolve_tesseract_cmd


def main() -> None:
    st.set_page_config(
        page_title="DocuMind - Intelligent Document Verification",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    settings = get_settings()
    app_state = get_app_state()
    ocr_available = is_tesseract_available(settings)
    tesseract_cmd = resolve_tesseract_cmd(settings)

    # Header section
    st.title("📄 DocuMind")
    st.caption(
        "Intelligent Document Extraction, Business Rule Verification & Human Review Workflow"
    )

    # Diagnostic pills & status overview
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            "System Status",
            "Operational",
            f"DocuMind v{__version__}",
        )
    with c2:
        st.metric(
            "Documents Ingested",
            len(app_state.extractions),
            f"{len(app_state.validations)} Validated",
        )
    with c3:
        reviews = app_state.review_service.list_reviews()
        pending = sum(1 for r in reviews if r.status.value in {"PENDING", "IN_REVIEW"})
        st.metric(
            "Active Review Queue",
            pending,
            f"{len(reviews)} Total Reviews",
        )
    with c4:
        ocr_label = "Active (Tesseract 5.4)" if ocr_available else "Not Configured"
        st.metric(
            "Local OCR Engine",
            ocr_label,
            f"DPI {settings.ocr_dpi}",
            help=f"Resolved binary: {tesseract_cmd}",
        )

    st.markdown("---")

    # Quick Action Navigation Cards
    st.markdown("### 🚀 Workflow Navigation")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        with st.container(border=True):
            st.markdown("#### 📥 02. Upload Invoices")
            st.caption(
                "Securely upload single or batch PDF invoices. Evaluates file integrity, page counts, "
                "PDF magic bytes, and runs the hybrid extraction and validation pipeline."
            )
            st.page_link("pages/02_Upload_Invoices.py", label="Go to Upload Portal", icon="📤")

    with col_b:
        with st.container(border=True):
            st.markdown("#### 🔍 04. Review Workbench")
            st.caption(
                "Interactive review workspace. Inspect high-resolution PDF pages with live spatial "
                "evidence overlays, review business discrepancies, and submit field corrections."
            )
            st.page_link("pages/04_Review_Workbench.py", label="Open Review Workbench", icon="🔎")

    with col_c:
        with st.container(border=True):
            st.markdown("#### 📊 01. Operational Dashboard")
            st.caption(
                "Real-time analytics on document processing throughput, validation status distributions, "
                "discrepancy taxonomies, and recent reviewer decisions."
            )
            st.page_link("pages/01_Dashboard.py", label="View Operational Dashboard", icon="📈")

    col_d, col_e, col_f = st.columns(3)

    with col_d:
        with st.container(border=True):
            st.markdown("#### 📁 03. Document Explorer")
            st.caption(
                "Filterable and searchable registry of all ingested invoices. Drill down into "
                "canonical header fields, line-item tables, and validation history."
            )
            st.page_link("pages/03_Document_Explorer.py", label="Explore Invoices", icon="📋")

    with col_e:
        with st.container(border=True):
            st.markdown("#### 🛡️ 06. Audit History")
            st.caption(
                "Chronological, immutable event stream tracking document lifecycle changes, "
                "reviewer assignments, field corrections, and approval decisions."
            )
            st.page_link("pages/06_Audit_History.py", label="Inspect Audit Trail", icon="📜")

    with col_f:
        with st.container(border=True):
            st.markdown("#### ⚙️ 07. Settings & Exports")
            st.caption(
                "Configure pipeline thresholds, verify OCR binary paths, load sample synthetic "
                "invoice batches, and download sanitized CSV/JSON audit reports."
            )
            st.page_link("pages/07_Settings.py", label="Settings & Export Center", icon="💾")

    # Sample corpus quick-load helper if empty
    if not app_state.extractions:
        st.markdown("---")
        with st.container(border=True):
            st.markdown("#### 💡 Quick Start: Pre-load Synthetic Invoice Corpus")
            st.caption(
                "Your application repository is currently empty. You can instantly load 10 sample invoices "
                "(including digital PDFs, scanned documents, arithmetic errors, and missing fields) to explore all UI capabilities."
            )
            if st.button("📥 Load 10 Sample Synthetic Invoices", type="primary"):
                with st.spinner("Ingesting, extracting, and validating 10 synthetic invoices..."):
                    loaded = app_state.load_synthetic_corpus_sample(limit=10)
                    st.success(
                        f"Successfully loaded {loaded} synthetic invoices! Explore the workbench now."
                    )
                    st.rerun()


if __name__ == "__main__":
    main()
