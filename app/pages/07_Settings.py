"""Settings, Diagnostics & Export Center page for DocuMind.

Provides engine configuration inspection, sample corpus batch ingestion tools,
and export downloads for processing summaries, validation results, corrections, and audit logs.
"""

from datetime import datetime, timezone

import streamlit as st
from app.services.state import get_app_state

from documind import __version__
from documind.config import get_settings
from documind.extraction.ocr import is_tesseract_available, resolve_tesseract_cmd
from documind.reporting.exporters import (
    AuditHistoryExporter,
    CorrectionHistoryExporter,
    DiscrepancyReportExporter,
    ProcessingSummaryExporter,
    ReviewOutcomeExporter,
)

UTC = timezone.utc

st.set_page_config(
    page_title="Settings & Exports - DocuMind",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ System Diagnostics & Export Center")
st.caption(
    "Central administration for OCR engine diagnostics, pipeline parameters, sample data ingestion, "
    "and sanitized audit and operational data exports."
)

settings = get_settings()
app_state = get_app_state()

# -----------------------------------------------------------------------------
# Section 1: Engine Diagnostics & Environment Configuration
# -----------------------------------------------------------------------------
st.markdown("### 🖥️ Engine & Environment Diagnostics")

tess_available = is_tesseract_available(settings)
tess_cmd = resolve_tesseract_cmd(settings)

c_diag1, c_diag2 = st.columns(2)

with c_diag1:
    with st.container(border=True):
        st.markdown("##### Optical Character Recognition (OCR)")
        st.write(
            f"- **Engine Status:** `{'✅ Available (Tesseract 5.4)' if tess_available else '❌ Not Found'}`"
        )
        st.write(f"- **Resolved Binary:** `{tess_cmd or 'Not configured'}`")
        st.write(f"- **OCR Rasterization DPI:** `{settings.ocr_dpi}`")
        st.write(f"- **Page Segmentation Mode (PSM):** `{settings.ocr_psm}`")
        st.write(f"- **OCR Execution Timeout:** `{settings.ocr_timeout_seconds}s`")

with c_diag2:
    with st.container(border=True):
        st.markdown("##### Ingestion & Pipeline Configuration")
        st.write(f"- **Environment:** `{settings.env}` | **DocuMind Version:** `v{__version__}`")
        st.write(f"- **Max Upload Size:** `{settings.max_upload_size_mb} MB`")
        st.write(f"- **Max Page Count:** `{settings.max_page_count} pages`")
        st.write(f"- **Routing Min Characters:** `{settings.routing_min_char_count}`")
        st.write(f"- **Routing Min Alpha Ratio:** `{settings.routing_min_alpha_ratio}`")
        st.write(f"- **Storage Path:** `{settings.storage_dir}`")

st.markdown("---")

# -----------------------------------------------------------------------------
# Section 2: Data Management & Corpus Loading
# -----------------------------------------------------------------------------
st.markdown("### 📦 Data Repository Management")
st.caption("Manage local document store and pre-load validated synthetic invoices for testing.")

col_btn1, col_btn2, col_btn3 = st.columns(3)

with col_btn1:
    if st.button("📥 Load 10 Sample Invoices", use_container_width=True):
        with st.spinner("Ingesting 10 synthetic invoices..."):
            loaded = app_state.load_synthetic_corpus_sample(limit=10)
            st.success(f"Ingested {loaded} invoices!")
            st.rerun()

with col_btn2:
    if st.button("📚 Load All 50 Corpus Invoices", use_container_width=True):
        with st.spinner("Ingesting all 50 corpus invoices (Digital vector & Scanned OCR)..."):
            loaded = app_state.load_synthetic_corpus_sample(limit=50)
            st.success(f"Ingested all {loaded} invoices!")
            st.rerun()

with col_btn3:
    if st.button("🗑️ Reset Application State", use_container_width=True, type="secondary"):
        with st.spinner("Resetting in-memory state..."):
            with app_state._lock:
                app_state.extractions.clear()
                app_state.validations.clear()
                app_state.documents.clear()
                app_state.review_service._reviews.clear()
                app_state.review_service._document_reviews.clear()
                app_state.audit_trail._events.clear()
            app_state.save_to_disk()
            st.warning("Application state cleared.")
            st.rerun()

st.markdown("---")

# -----------------------------------------------------------------------------
# Section 3: Reporting & Export Center
# -----------------------------------------------------------------------------
st.markdown("### 📤 Reporting & Export Downloads")
st.caption(
    "Export operational summaries, validation results, corrections, and audit histories. "
    "All CSV downloads apply formula-injection escaping (`'`) to protect spreadsheet viewers."
)

st.info(
    "🛡️ **Compliance Notice**: Exports reflect internal operational records and are not legally certified audit documents."
)

extractions = list(app_state.extractions.values())
validations = list(app_state.validations.values())
reviews = app_state.review_service.list_reviews()
audit_events = app_state.audit_trail.get_events()

timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

if not extractions:
    st.warning("No documents available to export. Ingest documents to enable data exports.")
else:
    e_col1, e_col2 = st.columns(2)

    with e_col1:
        with st.container(border=True):
            st.markdown("##### 1. Processing & Extraction Summary")
            st.caption("Document list, vendor, invoice numbers, totals, and validation statuses.")

            csv_proc = ProcessingSummaryExporter.to_csv(extractions, validations, reviews)
            json_proc = ProcessingSummaryExporter.to_json(extractions, validations, reviews)

            b1, b2 = st.columns(2)
            with b1:
                st.download_button(
                    "📄 Download CSV",
                    data=csv_proc,
                    file_name=f"documind_processing_summary_{timestamp_str}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with b2:
                st.download_button(
                    "📦 Download JSON",
                    data=json_proc,
                    file_name=f"documind_processing_summary_{timestamp_str}.json",
                    mime="application/json",
                    use_container_width=True,
                )

        with st.container(border=True):
            st.markdown("##### 2. Validation Discrepancy Registry")
            st.caption(
                "Granular catalogue of all identified rule failures, arithmetic variances, and missing fields."
            )

            csv_disc = DiscrepancyReportExporter.to_csv(validations)
            json_disc = DiscrepancyReportExporter.to_json(validations)

            b1, b2 = st.columns(2)
            with b1:
                st.download_button(
                    "📄 Download CSV",
                    data=csv_disc,
                    file_name=f"documind_discrepancies_{timestamp_str}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with b2:
                st.download_button(
                    "📦 Download JSON",
                    data=json_disc,
                    file_name=f"documind_discrepancies_{timestamp_str}.json",
                    mime="application/json",
                    use_container_width=True,
                )

    with e_col2:
        with st.container(border=True):
            st.markdown("##### 3. Human Review Outcomes & Decisions")
            st.caption(
                "Review records, approval/rejection status, assigned reviewer, and completion timestamps."
            )

            csv_rev = ReviewOutcomeExporter.to_csv(reviews)
            json_rev = ReviewOutcomeExporter.to_json(reviews)

            b1, b2 = st.columns(2)
            with b1:
                st.download_button(
                    "📄 Download CSV",
                    data=csv_rev,
                    file_name=f"documind_review_outcomes_{timestamp_str}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with b2:
                st.download_button(
                    "📦 Download JSON",
                    data=json_rev,
                    file_name=f"documind_review_outcomes_{timestamp_str}.json",
                    mime="application/json",
                    use_container_width=True,
                )

        with st.container(border=True):
            st.markdown("##### 4. Field Correction Audit History")
            st.caption(
                "Chronological list of proposed, accepted, and rejected reviewer field corrections."
            )

            csv_corr = CorrectionHistoryExporter.to_csv(reviews)

            st.download_button(
                "📄 Download Corrections CSV",
                data=csv_corr,
                file_name=f"documind_corrections_{timestamp_str}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with st.container(border=True):
            st.markdown("##### 5. Immutable Audit Event History")
            st.caption("Append-only log of every state change, reviewer action, and correction.")

            csv_audit = AuditHistoryExporter.to_csv(audit_events)
            json_audit = AuditHistoryExporter.to_json(audit_events)

            b1, b2 = st.columns(2)
            with b1:
                st.download_button(
                    "📄 Download CSV",
                    data=csv_audit,
                    file_name=f"documind_audit_events_{timestamp_str}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with b2:
                st.download_button(
                    "📦 Download JSON",
                    data=json_audit,
                    file_name=f"documind_audit_events_{timestamp_str}.json",
                    mime="application/json",
                    use_container_width=True,
                )
