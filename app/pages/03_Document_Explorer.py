"""Document Explorer page for DocuMind.

Provides searchable, filterable invoice registry with detail inspection of
extracted header fields, grounding evidence provenance, discrepancies, and review state.
"""

import pandas as pd
import streamlit as st
from app.services.state import get_app_state

st.set_page_config(
    page_title="Document Explorer - DocuMind",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Document Explorer")
st.caption(
    "Search, filter, and drill down into extracted invoice metadata, evidence grounding, and verification audits."
)

app_state = get_app_state()
extractions = list(app_state.extractions.values())

if not extractions:
    st.info("ℹ️ No documents registered yet. Upload documents or load synthetic samples to explore.")
    if st.button("📥 Load 10 Sample Invoices", type="primary"):
        with st.spinner("Ingesting sample invoices..."):
            loaded = app_state.load_synthetic_corpus_sample(limit=10)
            st.success(f"Loaded {loaded} synthetic invoices!")
            st.rerun()
    st.stop()

# Filters Row
f_col1, f_col2, f_col3, f_col4 = st.columns([2, 1, 1, 1])

with f_col1:
    search_query = (
        st.text_input(
            "🔍 Search (Document ID, Invoice #, or Vendor)",
            placeholder="e.g. DOC-SYN-001, INV-2024, Apex...",
        )
        .strip()
        .lower()
    )

with f_col2:
    val_status_options = ["All", "VALID", "VALID_WITH_WARNINGS", "NEEDS_REVIEW", "INVALID"]
    filter_val = st.selectbox("Validation Status", val_status_options)

with f_col3:
    rev_status_options = [
        "All",
        "PENDING",
        "IN_REVIEW",
        "CORRECTION_REQUESTED",
        "APPROVED",
        "REJECTED",
        "RETURNED_FOR_REVIEW",
    ]
    filter_rev = st.selectbox("Review Status", rev_status_options)

with f_col4:
    filter_type = st.selectbox("Source Type", ["All", "Digital", "Scanned (OCR)"])

# Filter logic
filtered_records = []
for ext in extractions:
    doc_id = ext.document_id
    val = app_state.validations.get(doc_id)
    rev = app_state.review_service.get_active_review_for_document(doc_id)
    rf = ext.raw_fields

    val_status = val.overall_status.value if val else "NOT_VALIDATED"
    rev_status = rev.status.value if rev else "NO_REVIEW"
    is_scanned = "scanned" in ext.file_name.lower()

    # Search filter
    if search_query:
        searchable_text = (
            f"{doc_id} {rf.get('invoice_number', '')} {rf.get('vendor_name', '')}".lower()
        )
        if search_query not in searchable_text:
            continue

    # Validation filter
    if filter_val != "All" and val_status != filter_val:
        continue

    # Review filter
    if filter_rev != "All" and rev_status != filter_rev:
        continue

    # Source filter
    if filter_type == "Digital" and is_scanned:
        continue
    if filter_type == "Scanned (OCR)" and not is_scanned:
        continue

    filtered_records.append((ext, val, rev))

st.write(f"Showing **{len(filtered_records)}** of **{len(extractions)}** documents")

# Table view
table_rows = []
for ext, val, rev in filtered_records:
    rf = ext.raw_fields
    table_rows.append(
        {
            "Document ID": ext.document_id,
            "File Name": ext.file_name,
            "Vendor": rf.get("vendor_name") or "⚠️ [MISSING]",
            "Invoice #": rf.get("invoice_number") or "⚠️ [MISSING]",
            "Date": str(rf.get("invoice_date", "—")),
            "Currency": rf.get("currency", "USD"),
            "Total": f"{rf.get('total', 0.00)}",
            "Validation Status": val.overall_status.value if val else "—",
            "Review Status": rev.status.value if rev else "—",
            "Reviewer": rev.assigned_reviewer or "Unassigned" if rev else "—",
        }
    )

if table_rows:
    df_table = pd.DataFrame(table_rows)
    st.dataframe(df_table, use_container_width=True)

st.markdown("---")

# Document Detail View Selector
st.markdown("### 🔍 Document Detail Inspection")
doc_ids = [ext.document_id for ext, _, _ in filtered_records]
if not doc_ids:
    st.info("No matching documents found with current filters.")
    st.stop()

selected_doc_id = st.selectbox("Select document to inspect details:", doc_ids)
selected_ext = app_state.extractions[selected_doc_id]
selected_val = app_state.validations.get(selected_doc_id)
selected_rev = app_state.review_service.get_active_review_for_document(selected_doc_id)

col_d1, col_d2 = st.columns([2, 1])

with col_d1:
    st.markdown(f"#### Document Metadata: `{selected_doc_id}`")
    rf = selected_ext.raw_fields

    m_c1, m_c2, m_c3, m_c4 = st.columns(4)
    with m_c1:
        st.write(f"**Invoice #:** `{rf.get('invoice_number') or 'NOT SPECIFIED'}`")
        st.write(f"**Date:** `{rf.get('invoice_date') or 'NOT SPECIFIED'}`")
    with m_c2:
        st.write(f"**Vendor:** `{rf.get('vendor_name') or 'NOT SPECIFIED'}`")
        st.write(f"**Due Date:** `{rf.get('due_date') or 'NOT SPECIFIED'}`")
    with m_c3:
        st.write(f"**Currency:** `{rf.get('currency') or 'USD'}`")
        st.write(f"**Subtotal:** `{rf.get('subtotal') or '—'}`")
    with m_c4:
        st.write(f"**Tax:** `{rf.get('tax') or rf.get('tax_amount') or '0.00'}`")
        st.write(f"**Total:** `{rf.get('total') or '0.00'}`")

    # Line items
    line_items = rf.get("line_items", [])
    if line_items:
        st.markdown("##### Extracted Line Items")
        item_rows = []
        for idx, item in enumerate(line_items):
            item_rows.append(
                {
                    "#": idx + 1,
                    "Description": item.description,
                    "Qty": item.quantity if item.quantity is not None else "—",
                    "Unit Price": item.unit_price if item.unit_price is not None else "—",
                    "Line Total": item.total if item.total is not None else "—",
                }
            )
        st.dataframe(pd.DataFrame(item_rows), use_container_width=True)

with col_d2:
    st.markdown("#### Verification Status")
    if selected_val:
        v_status = selected_val.overall_status.value
        if v_status == "VALID":
            st.success(f"Status: **{v_status}**")
        elif v_status == "VALID_WITH_WARNINGS":
            st.info(f"Status: **{v_status}**")
        elif v_status == "NEEDS_REVIEW":
            st.warning(f"Status: **{v_status}**")
        else:
            st.error(f"Status: **{v_status}**")

        st.write(f"- Rules Evaluated: `{selected_val.rules_evaluated}`")
        st.write(f"- Rules Passed: `{selected_val.rules_passed}`")
        st.write(f"- Discrepancies: `{len(selected_val.discrepancies)}`")

        if selected_val.discrepancies:
            st.markdown("##### Active Discrepancies")
            for d in selected_val.discrepancies:
                st.caption(f"**[{d.severity.value}] {d.rule_id}**: {d.explanation}")

    st.markdown("---")
    st.page_link(
        "pages/04_Review_Workbench.py",
        label=f"Open {selected_doc_id} in Review Workbench",
        icon="🔎",
    )
