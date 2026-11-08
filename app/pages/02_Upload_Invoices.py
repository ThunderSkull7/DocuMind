"""Invoice Upload and Ingestion Processing Portal for DocuMind.

Executes file validation, binary signature checks, size constraints,
hybrid text extraction, business rule validation, and review record initialization.
"""

import streamlit as st
from app.services.state import get_app_state

from documind.config import get_settings

st.set_page_config(
    page_title="Upload Invoices - DocuMind",
    page_icon="📥",
    layout="wide",
)

st.title("📥 Invoice Upload & Ingestion Portal")
st.caption(
    "Secure document ingestion adhering to enterprise AP policies: PDF magic bytes verification, "
    "size thresholds, SHA-256 integrity hashing, and automated business rule screening."
)

settings = get_settings()
app_state = get_app_state()

# File Uploader
uploaded_files = st.file_uploader(
    "Choose invoice PDF files to process",
    type=["pdf"],
    accept_multiple_files=True,
    help=f"Accepts PDF files up to {settings.max_upload_size_mb} MB and {settings.max_page_count} pages.",
)

# Reviewer identity
reviewer_name = st.text_input(
    "Submitting Actor / Reviewer Name",
    value="reviewer_ap",
    help="Identifies the operator in append-only audit events.",
)

if uploaded_files:
    if st.button(f"🚀 Ingest and Process {len(uploaded_files)} Invoices", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        success_count = 0
        failure_count = 0

        for idx, file_obj in enumerate(uploaded_files):
            status_text.text(f"Processing ({idx + 1}/{len(uploaded_files)}): {file_obj.name}...")
            content = file_obj.read()

            success, msg, doc_id = app_state.process_document_bytes(
                content=content,
                filename=file_obj.name,
                actor=reviewer_name.strip() or "reviewer_ap",
            )

            progress_bar.progress((idx + 1) / len(uploaded_files))

            if success and doc_id:
                success_count += 1
                val = app_state.validations.get(doc_id)
                ext = app_state.extractions.get(doc_id)
                rf = ext.raw_fields if ext else {}

                status_icon = "✅" if val and val.overall_status.value == "VALID" else "⚠️"
                with st.expander(
                    f"{status_icon} `{doc_id}` — {file_obj.name} ({val.overall_status.value if val else 'PROCESSED'})",
                    expanded=True,
                ):
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.write(f"**Vendor:** `{rf.get('vendor_name') or 'MISSING'}`")
                    with c2:
                        st.write(f"**Invoice #:** `{rf.get('invoice_number') or 'MISSING'}`")
                    with c3:
                        st.write(
                            f"**Total:** `{rf.get('currency', '$')} {rf.get('total', '0.00')}`"
                        )
                    with c4:
                        st.write(f"**Validation:** `{val.overall_status.value if val else '—'}`")

                    if val and val.discrepancies:
                        st.warning(
                            f"Identified {len(val.discrepancies)} discrepancies requiring review:"
                        )
                        for d in val.discrepancies[:3]:
                            st.write(f"- `[{d.severity.value}]` **{d.rule_id}**: {d.explanation}")
                        if len(val.discrepancies) > 3:
                            st.caption(f"...and {len(val.discrepancies) - 3} more.")
            else:
                failure_count += 1
                st.error(f"❌ Failed to ingest `{file_obj.name}`: {msg}")

        status_text.empty()
        progress_bar.empty()

        st.success(
            f"Processing Complete! Successfully processed: {success_count} | Failures: {failure_count}"
        )
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            st.page_link("pages/04_Review_Workbench.py", label="Open Review Workbench", icon="🔎")
        with col_nav2:
            st.page_link("pages/03_Document_Explorer.py", label="View Document Explorer", icon="📋")

st.markdown("---")

# Quick Load Corpus Helper
st.markdown("### 📦 Corpus Ingestion Shortcut")
st.caption("Quickly ingest synthetic invoices directly from the verified project corpus:")
c_btn1, c_btn2 = st.columns(2)

with c_btn1:
    if st.button("📥 Ingest 10 Digital & Scanned Invoices"):
        with st.spinner("Ingesting 10 synthetic invoices from data/synthetic_documents..."):
            loaded = app_state.load_synthetic_corpus_sample(limit=10)
            st.success(f"Ingested {loaded} synthetic invoices!")
            st.rerun()

with c_btn2:
    if st.button("📚 Ingest All 50 Corpus Invoices"):
        with st.spinner("Ingesting complete 50-invoice corpus (Digital & Scanned with OCR)..."):
            loaded = app_state.load_synthetic_corpus_sample(limit=50)
            st.success(f"Ingested all {loaded} corpus invoices into review queue!")
            st.rerun()
