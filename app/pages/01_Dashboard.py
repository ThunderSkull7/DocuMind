"""Operational Dashboard page for DocuMind.

Displays real-time throughput metrics, validation status distributions, discrepancy
taxonomies, and recent human review decisions across all processed documents.
"""

import pandas as pd
import streamlit as st
from app.services.state import get_app_state

from documind.review.models import ReviewStatus
from documind.validation.models import OverallValidationStatus

st.set_page_config(
    page_title="Dashboard - DocuMind",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Operational Dashboard")
st.caption(
    "Real-time accounts payable invoice processing metrics, verification outcomes, and review queue status."
)

app_state = get_app_state()
extractions = list(app_state.extractions.values())
validations = list(app_state.validations.values())
reviews = app_state.review_service.list_reviews()

# Empty State
if not extractions:
    st.info(
        "ℹ️ No documents processed yet. Upload invoice PDFs or pre-load sample synthetic invoices to view analytics."
    )
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("📥 Load 10 Sample Synthetic Invoices", type="primary"):
            with st.spinner("Ingesting sample invoices..."):
                loaded = app_state.load_synthetic_corpus_sample(limit=10)
                st.success(f"Loaded {loaded} synthetic invoices!")
                st.rerun()
    with c2:
        st.page_link("pages/02_Upload_Invoices.py", label="Or Go to Upload Portal", icon="📤")
    st.stop()

# Key Metric Cards
m1, m2, m3, m4, m5, m6 = st.columns(6)

pending_reviews = sum(1 for r in reviews if r.status == ReviewStatus.PENDING)
in_review = sum(1 for r in reviews if r.status == ReviewStatus.IN_REVIEW)
approved = sum(1 for r in reviews if r.status == ReviewStatus.APPROVED)
rejected = sum(1 for r in reviews if r.status == ReviewStatus.REJECTED)
correction_req = sum(1 for r in reviews if r.status == ReviewStatus.CORRECTION_REQUESTED)

with m1:
    st.metric("Total Processed", len(extractions))
with m2:
    st.metric("Awaiting Review", pending_reviews + in_review, f"{pending_reviews} Pending")
with m3:
    st.metric(
        "Approved Invoices",
        approved,
        f"{(approved / len(reviews) * 100):.1f}%" if reviews else "0%",
    )
with m4:
    st.metric("Rejected Invoices", rejected)
with m5:
    st.metric("Correction Needed", correction_req)
with m6:
    total_discrepancies = sum(len(v.discrepancies) for v in validations)
    st.metric("Discrepancies", total_discrepancies)

st.markdown("---")

# Visual Analytics Row
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("#### 📋 Review Status Distribution")
    status_counts = {
        "Pending": pending_reviews,
        "In Review": in_review,
        "Correction Req": correction_req,
        "Approved": approved,
        "Rejected": rejected,
    }
    df_status = pd.DataFrame(list(status_counts.items()), columns=["Status", "Count"]).set_index(
        "Status"
    )
    st.bar_chart(df_status, color="#3b82f6")

with col_chart2:
    st.markdown("#### 🛡️ Validation Outcome Distribution")
    val_counts = {
        "VALID": sum(1 for v in validations if v.overall_status == OverallValidationStatus.VALID),
        "WARNINGS": sum(
            1
            for v in validations
            if v.overall_status == OverallValidationStatus.VALID_WITH_WARNINGS
        ),
        "NEEDS_REVIEW": sum(
            1 for v in validations if v.overall_status == OverallValidationStatus.NEEDS_REVIEW
        ),
        "INVALID": sum(
            1 for v in validations if v.overall_status == OverallValidationStatus.INVALID
        ),
    }
    df_val = pd.DataFrame(
        list(val_counts.items()), columns=["Validation Status", "Count"]
    ).set_index("Validation Status")
    st.bar_chart(df_val, color="#f59e0b")

# Document Source & Discrepancy Breakdown
st.markdown("---")
c_src, c_disc = st.columns(2)

with c_src:
    st.markdown("#### 📄 Document Ingestion Source")
    # Identify digital vs scanned
    scanned_count = sum(1 for ext in extractions if "scanned" in ext.file_name.lower())
    digital_count = len(extractions) - scanned_count
    st.write(
        f"- **Native Digital PDFs**: `{digital_count}` ({(digital_count / len(extractions) * 100):.1f}%)\n"
        f"- **Scanned Image PDFs (OCR)**: `{scanned_count}` ({(scanned_count / len(extractions) * 100):.1f}%)"
    )

with c_disc:
    st.markdown("#### ⚠️ Discrepancy Categories")
    cat_counts: dict[str, int] = {}
    for v in validations:
        for d in v.discrepancies:
            cat_name = d.category.value.title()
            cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1

    if cat_counts:
        df_cats = pd.DataFrame(list(cat_counts.items()), columns=["Category", "Count"]).set_index(
            "Category"
        )
        st.dataframe(df_cats, use_container_width=True)
    else:
        st.success("No discrepancies identified across processed invoices.")

# Recent Documents Table
st.markdown("---")
st.markdown("### 🕒 Recent Invoices & Review Routing")

recent_rows = []
for ext in reversed(extractions[-10:]):
    doc_id = ext.document_id
    val = app_state.validations.get(doc_id)
    rev = app_state.review_service.get_active_review_for_document(doc_id)

    rf = ext.raw_fields
    recent_rows.append(
        {
            "Document ID": doc_id,
            "File Name": ext.file_name,
            "Vendor": rf.get("vendor_name") or "—",
            "Invoice #": rf.get("invoice_number") or "—",
            "Total": f"{rf.get('currency', '$')} {rf.get('total', 0.00)}",
            "Validation Status": val.overall_status.value if val else "—",
            "Review Status": rev.status.value if rev else "—",
            "Reviewer": rev.assigned_reviewer or "Unassigned" if rev else "—",
        }
    )

if recent_rows:
    st.dataframe(pd.DataFrame(recent_rows), use_container_width=True)
    st.page_link(
        "pages/04_Review_Workbench.py", label="Open Pending Invoices in Review Workbench", icon="🔎"
    )
