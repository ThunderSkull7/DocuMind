"""Validation Reports & Discrepancy Analytics page for DocuMind.

Presents multi-dimensional compliance reports, rule catalogue hit rates,
arithmetic variance audits, and severity-categorized discrepancy drill-downs.
"""

import pandas as pd
import streamlit as st
from app.services.state import get_app_state

from documind.validation.models import OverallValidationStatus

st.set_page_config(
    page_title="Validation Reports - DocuMind",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Business Rule Validation & Discrepancy Analytics")
st.caption(
    "Comprehensive verification reports evaluated by DocuMind's deterministic business rules engine: "
    "line-item arithmetic, sales tax consistency, mandatory fields, duplicate screening, and ERP reference matching."
)

app_state = get_app_state()
validations = list(app_state.validations.values())

if not validations:
    st.info("ℹ️ No validation data available. Ingest documents to view reports.")
    st.stop()

# Aggregate Metrics
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Total Validated", len(validations))
with c2:
    valid_count = sum(1 for v in validations if v.overall_status == OverallValidationStatus.VALID)
    st.metric("Clean Pass", valid_count, f"{(valid_count / len(validations) * 100):.1f}%")
with c3:
    warn_count = sum(
        1 for v in validations if v.overall_status == OverallValidationStatus.VALID_WITH_WARNINGS
    )
    st.metric("With Warnings", warn_count)
with c4:
    review_count = sum(
        1 for v in validations if v.overall_status == OverallValidationStatus.NEEDS_REVIEW
    )
    st.metric("Needs Review", review_count)
with c5:
    invalid_count = sum(
        1 for v in validations if v.overall_status == OverallValidationStatus.INVALID
    )
    st.metric("Invalid (Missing Data)", invalid_count)

st.markdown("---")

# Rule Catalogue Summary Table
st.markdown("### 📋 Active Rule Catalogue Performance")

rule_occurrences: dict[str, dict] = {}
for v in validations:
    for d in v.discrepancies:
        r_id = d.rule_id
        if r_id not in rule_occurrences:
            rule_occurrences[r_id] = {
                "Rule ID": r_id,
                "Rule Name": d.rule_name,
                "Category": d.category.value.title(),
                "Severity": d.severity.value,
                "Triggered Invoices": set(),
                "Occurrences": 0,
            }
        rule_occurrences[r_id]["Triggered Invoices"].add(d.document_id)
        rule_occurrences[r_id]["Occurrences"] += 1

if rule_occurrences:
    table_rules = []
    for r in rule_occurrences.values():
        table_rules.append(
            {
                "Rule ID": r["Rule ID"],
                "Rule Name": r["Rule Name"],
                "Category": r["Category"],
                "Severity": r["Severity"],
                "Affected Documents": len(r["Triggered Invoices"]),
                "Total Hits": r["Occurrences"],
                "Sample Invoices": ", ".join(list(r["Triggered Invoices"])[:3]),
            }
        )
    st.dataframe(pd.DataFrame(table_rules), use_container_width=True)
else:
    st.success("No validation rules triggered! All evaluated invoices are compliant.")

st.markdown("---")

# Granular Discrepancies Table with Filter
st.markdown("### ⚠️ Detailed Discrepancy Registry")

all_discrepancies = [d for v in validations for d in v.discrepancies]

if all_discrepancies:
    f_c1, f_c2 = st.columns(2)
    with f_c1:
        selected_severity = st.selectbox(
            "Filter by Severity:",
            ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
        )
    with f_c2:
        categories = ["All"] + sorted({d.category.value.title() for d in all_discrepancies})
        selected_category = st.selectbox("Filter by Category:", categories)

    filtered_discs = []
    for d in all_discrepancies:
        if selected_severity != "All" and d.severity.value != selected_severity:
            continue
        if selected_category != "All" and d.category.value.title() != selected_category:
            continue
        filtered_discs.append(
            {
                "Document ID": d.document_id,
                "Rule ID": d.rule_id,
                "Severity": d.severity.value,
                "Category": d.category.value.title(),
                "Explanation": d.explanation,
                "Expected": str(d.expected_value or "—"),
                "Actual": str(d.actual_value or "—"),
                "Delta": str(d.difference or "—"),
                "Recommendation": d.review_recommendation or "—",
            }
        )

    st.write(f"Displaying **{len(filtered_discs)}** of **{len(all_discrepancies)}** discrepancies")
    if filtered_discs:
        st.dataframe(pd.DataFrame(filtered_discs), use_container_width=True)
else:
    st.info("Zero active discrepancies recorded.")
