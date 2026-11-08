"""Interactive Human Review Workbench for DocuMind.

Enables accounts payable reviewers to inspect high-resolution invoice PDF pages
with live spatial evidence overlays, examine business rule discrepancies, propose and
accept field corrections, trigger re-validation, and record approval/rejection decisions.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

import streamlit as st
from app.components.pdf_viewer import render_pdf_page
from app.services.state import get_app_state

from documind.exceptions import (
    InvalidCorrectionError,
    ReviewConcurrencyError,
    UnresolvedDiscrepancyError,
)
from documind.review.models import (
    CorrectionStatus,
    ReviewStatus,
)
from documind.schemas.invoice import (
    BoundingBox,
    EvidenceStatus,
)
from documind.validation.models import (
    OverallValidationStatus,
)

st.set_page_config(
    page_title="Review Workbench - DocuMind",
    page_icon="🔎",
    layout="wide",
)

app_state = get_app_state()
extractions = list(app_state.extractions.values())

if not extractions:
    st.info(
        "ℹ️ No documents in the review queue. Upload documents or load synthetic samples to begin."
    )
    if st.button("📥 Load 10 Sample Invoices", type="primary"):
        with st.spinner("Ingesting sample invoices..."):
            loaded = app_state.load_synthetic_corpus_sample(limit=10)
            st.success(f"Loaded {loaded} synthetic invoices!")
            st.rerun()
    st.stop()

# Top queue selector
st.markdown("### 🔎 Accounts Payable Review Workbench")

# Review queue filter tabs
queue_tab_options = [
    "All Active",
    "Needs Review / Invalid",
    "Pending",
    "In Review",
    "Approved",
    "Rejected",
]
selected_queue_filter = st.radio(
    "Queue Filter:",
    queue_tab_options,
    horizontal=True,
    label_visibility="collapsed",
)

eligible_docs = []
for ext in extractions:
    doc_id = ext.document_id
    val = app_state.validations.get(doc_id)
    rev = app_state.review_service.get_active_review_for_document(doc_id)
    r_status = rev.status if rev else ReviewStatus.PENDING
    v_status = val.overall_status if val else OverallValidationStatus.INDETERMINATE

    if selected_queue_filter == "Needs Review / Invalid":
        if v_status in {
            OverallValidationStatus.NEEDS_REVIEW,
            OverallValidationStatus.INVALID,
        } and r_status not in {
            ReviewStatus.APPROVED,
            ReviewStatus.REJECTED,
        }:
            eligible_docs.append(ext)
    elif selected_queue_filter == "Pending":
        if r_status == ReviewStatus.PENDING:
            eligible_docs.append(ext)
    elif selected_queue_filter == "In Review":
        if r_status in {
            ReviewStatus.IN_REVIEW,
            ReviewStatus.CORRECTION_REQUESTED,
            ReviewStatus.RETURNED_FOR_REVIEW,
        }:
            eligible_docs.append(ext)
    elif selected_queue_filter == "Approved":
        if r_status == ReviewStatus.APPROVED:
            eligible_docs.append(ext)
    elif selected_queue_filter == "Rejected":
        if r_status == ReviewStatus.REJECTED:
            eligible_docs.append(ext)
    else:  # All Active
        if r_status not in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
            eligible_docs.append(ext)

if not eligible_docs:
    eligible_docs = extractions  # Fallback to all if filter empty

doc_options = {
    ext.document_id: (
        f"{ext.document_id} — {ext.raw_fields.get('vendor_name') or 'MISSING VENDOR'} "
        f"({app_state.validations[ext.document_id].overall_status.value if ext.document_id in app_state.validations else '—'})"
    )
    for ext in eligible_docs
}

selected_doc_id = st.selectbox(
    "Select Document to Review:",
    options=list(doc_options.keys()),
    format_func=lambda d_id: doc_options.get(d_id, d_id),
)

# Fetch context for selected document
record = app_state.extractions[selected_doc_id]
initial_val = app_state.validations[selected_doc_id]
review = app_state.review_service.get_active_review_for_document(selected_doc_id)
if not review:
    review = app_state.review_service.create_review(record, initial_val)

# PDF path lookup
pdf_path = app_state.document_paths.get(selected_doc_id)
if not pdf_path or not pdf_path.is_file():
    # Fallback to synthetic documents directory if ingested directly
    candidate = Path("data/synthetic_documents") / record.file_name
    if candidate.is_file():
        pdf_path = candidate

# Session State for interactive bounding box highlight
highlight_key = f"highlight_field_{selected_doc_id}"
if highlight_key not in st.session_state:
    st.session_state[highlight_key] = None

selected_field_to_highlight = st.session_state[highlight_key]

# Compute active bounding box
active_highlight_box: BoundingBox | None = None
active_evidence_info: dict[str, Any] | None = None

if selected_field_to_highlight and selected_field_to_highlight in record.evidence:
    ev = record.evidence[selected_field_to_highlight]
    if ev.bounding_box and ev.status == EvidenceStatus.EXTRACTED:
        active_highlight_box = ev.bounding_box
        active_evidence_info = {
            "field": selected_field_to_highlight,
            "raw_text": ev.raw_text,
            "method": ev.method.value,
            "confidence": ev.confidence,
            "page": ev.bounding_box.page,
            "coords": f"[{ev.bounding_box.x0:.1f}, {ev.bounding_box.y0:.1f}, {ev.bounding_box.x1:.1f}, {ev.bounding_box.y1:.1f}] pt",
        }

# Status Header Banner
status_color = "#3b82f6"
if review.status == ReviewStatus.APPROVED:
    status_color = "#10b981"
elif review.status == ReviewStatus.REJECTED:
    status_color = "#ef4444"
elif initial_val.overall_status in {
    OverallValidationStatus.INVALID,
    OverallValidationStatus.NEEDS_REVIEW,
}:
    status_color = "#f59e0b"

st.markdown(
    f"""
    <div style="background-color: #1e293b; padding: 0.8rem 1.2rem; border-radius: 0.5rem; margin-bottom: 1rem; border-left: 5px solid {status_color}; display: flex; justify-content: space-between; align-items: center;">
        <div>
            <span style="font-weight: 700; color: #f8fafc; font-size: 1.1rem;">Invoice: {record.file_name}</span> &nbsp;|&nbsp;
            <span style="color: #94a3b8;">Review ID: <code>{review.review_id}</code></span> &nbsp;|&nbsp;
            <span style="color: #94a3b8;">Revision: <code>v{review.revision}</code></span>
        </div>
        <div>
            <span style="background-color: {status_color}33; color: {status_color}; padding: 0.3rem 0.8rem; border-radius: 0.25rem; font-weight: 600; font-size: 0.9rem;">
                Review: {review.status.value}
            </span> &nbsp;
            <span style="background-color: #334155; color: #f8fafc; padding: 0.3rem 0.8rem; border-radius: 0.25rem; font-weight: 600; font-size: 0.9rem;">
                Validation: {review.corrected_view.corrected_validation_result.overall_status.value if review.corrected_view and review.corrected_view.corrected_validation_result else initial_val.overall_status.value}
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Workbench Main Layout: Left = PDF Viewer, Right = Review Panels
col_viewer, col_panels = st.columns([1, 1], gap="medium")

# -----------------------------------------------------------------------------
# LEFT COLUMN: PDF Document Viewer with Evidence Overlays
# -----------------------------------------------------------------------------
with col_viewer:
    st.markdown("#### 📄 Document Viewer & Spatial Grounding")

    target_page = 1
    if active_highlight_box:
        target_page = active_highlight_box.page

    # Page navigation controls
    total_doc_pages = 1
    if pdf_path:
        import fitz

        with fitz.open(pdf_path) as _d:
            total_doc_pages = _d.page_count

    v_c1, v_c2, v_c3 = st.columns([1, 2, 1])
    with v_c1:
        selected_page = st.number_input(
            "Page", min_value=1, max_value=max(1, total_doc_pages), value=target_page, step=1
        )
    with v_c2:
        zoom_dpi = st.select_slider("Zoom DPI", options=[100, 150, 200], value=150)
    with v_c3:
        if st.button("Clear Highlight", use_container_width=True):
            st.session_state[highlight_key] = None
            st.rerun()

    # Render PDF page with spatial evidence highlight
    if pdf_path and pdf_path.is_file():
        page_img, meta = render_pdf_page(
            pdf_source=pdf_path,
            page_number=int(selected_page),
            highlight_box=active_highlight_box
            if active_highlight_box and active_highlight_box.page == int(selected_page)
            else None,
            dpi=zoom_dpi,
        )

        if page_img:
            st.image(page_img, use_container_width=True)

            # Coordinate & Provenance info bar
            if active_evidence_info and active_evidence_info["page"] == int(selected_page):
                st.info(
                    f"🎯 **Highlighting `{active_evidence_info['field']}`** | "
                    f"Page {active_evidence_info['page']} | "
                    f"Coordinates: `{active_evidence_info['coords']}` | "
                    f"Method: `{active_evidence_info['method']}` | "
                    f'Extracted: *"{active_evidence_info["raw_text"]}"*'
                )
            else:
                st.caption(
                    f"Page {selected_page} of {meta['total_pages']} | "
                    f"Dimensions: {meta['page_width_pt']:.1f} x {meta['page_height_pt']:.1f} pt | "
                    f"Select any field or discrepancy in the right panel to highlight its exact location."
                )
        else:
            st.error(f"Failed to render PDF page: {meta.get('error')}")
    else:
        st.warning(
            "Original PDF source file not located on disk. Showing evidence coordinate fallback:"
        )
        if active_evidence_info:
            st.code(active_evidence_info)

# -----------------------------------------------------------------------------
# RIGHT COLUMN: Extracted Fields, Discrepancies, Corrections, Decisions
# -----------------------------------------------------------------------------
with col_panels:
    tab_fields, tab_disc, tab_corr, tab_decision = st.tabs(
        ["📋 Extracted Fields", "⚠️ Discrepancies", "✏️ Corrections", "⚖️ Review Decision"]
    )

    # -------------------------------------------------------------------------
    # TAB 1: Extracted Fields
    # -------------------------------------------------------------------------
    with tab_fields:
        rf = record.raw_fields
        corrected_fields = review.corrected_view.effective_fields if review.corrected_view else rf

        st.markdown("##### Header & Identity Fields")

        def render_field_row(field_name: str, label: str):
            orig_val = rf.get(field_name)
            eff_val = corrected_fields.get(field_name)
            is_corrected = review.corrected_view is not None and eff_val != orig_val
            ev = record.evidence.get(field_name)

            col_label, col_val, col_action = st.columns([2, 3, 1])

            with col_label:
                st.markdown(f"**{label}**")

            with col_val:
                if eff_val is None or str(eff_val).strip() == "":
                    st.markdown(
                        "<span style='color: #ef4444; font-weight: 600;'>[MISSING]</span>",
                        unsafe_allow_html=True,
                    )
                elif ev and ev.status == EvidenceStatus.AMBIGUOUS:
                    st.markdown(
                        f"<span style='color: #f59e0b; font-weight: 600;'>{eff_val} [AMBIGUOUS]</span>",
                        unsafe_allow_html=True,
                    )
                elif is_corrected:
                    st.markdown(f"**{eff_val}** *(Corrected)*")
                else:
                    st.write(f"`{eff_val}`")

            with col_action:
                if ev and ev.bounding_box:
                    if st.button(
                        "📍 View", key=f"btn_hl_{field_name}", help="Highlight on document"
                    ):
                        st.session_state[highlight_key] = field_name
                        st.rerun()

        render_field_row("invoice_number", "Invoice Number")
        render_field_row("invoice_date", "Invoice Date")
        render_field_row("due_date", "Due Date")
        render_field_row("purchase_order_number", "PO Number")
        render_field_row("vendor_name", "Vendor Name")
        render_field_row("currency", "Currency")

        st.markdown("##### Financial Summary")
        render_field_row("subtotal", "Subtotal")
        render_field_row("tax", "Tax Amount")
        render_field_row("shipping_amount", "Shipping Fee")
        render_field_row("discount_amount", "Discount")
        render_field_row("total", "Invoice Total")

        # Line items
        line_items = rf.get("line_items", [])
        if line_items:
            st.markdown("##### Line Items Table")
            items_data = [
                {
                    "#": i + 1,
                    "Description": it.description,
                    "Qty": it.quantity,
                    "Unit Price": it.unit_price,
                    "Total": it.total,
                }
                for i, it in enumerate(line_items)
            ]
            import pandas as pd

            st.dataframe(pd.DataFrame(items_data), use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 2: Discrepancies
    # -------------------------------------------------------------------------
    with tab_disc:
        # Determine effective discrepancies (from corrected view if revalidated)
        effective_val_result = (
            review.corrected_view.corrected_validation_result
            if review.corrected_view and review.corrected_view.corrected_validation_result
            else initial_val
        )
        active_discrepancies = effective_val_result.discrepancies

        if not active_discrepancies:
            st.success(
                "✅ Zero active discrepancies! All business rules, completeness, and arithmetic checks passed."
            )
        else:
            st.warning(f"Found {len(active_discrepancies)} discrepancies requiring review:")

            for idx, disc in enumerate(active_discrepancies):
                sev = disc.severity.value
                sev_color = "#ef4444" if sev in {"CRITICAL", "HIGH"} else "#f59e0b"

                with st.expander(f"[{sev}] {disc.rule_id} — {disc.rule_name}", expanded=True):
                    st.markdown(f"**Explanation:** {disc.explanation}")

                    c_e1, c_e2, c_e3 = st.columns(3)
                    with c_e1:
                        st.caption(f"Category: `{disc.category.value}`")
                    with c_e2:
                        st.caption(f"Expected: `{disc.expected_value or '—'}`")
                    with c_e3:
                        st.caption(f"Actual: `{disc.actual_value or '—'}`")

                    if disc.difference is not None:
                        st.write(f"**Numerical Delta:** `{disc.difference}`")
                    if disc.review_recommendation:
                        st.info(f"💡 **Recommendation:** {disc.review_recommendation}")

                    # Button to highlight affected field on PDF
                    if disc.affected_fields:
                        first_field = disc.affected_fields[0]
                        if st.button(f"🎯 Highlight '{first_field}' on PDF", key=f"disc_hl_{idx}"):
                            st.session_state[highlight_key] = first_field
                            st.rerun()

    # -------------------------------------------------------------------------
    # TAB 3: Field Corrections
    # -------------------------------------------------------------------------
    with tab_corr:
        st.markdown("##### ✏️ Propose Field Correction")
        st.caption(
            "Reviewer corrections are stored independently without mutating original document extractions. "
            "Accepting a correction triggers an automated re-validation sweep."
        )

        all_fields = [
            "invoice_number",
            "invoice_date",
            "due_date",
            "vendor_name",
            "currency",
            "total",
            "subtotal",
            "tax",
            "shipping_amount",
            "discount_amount",
            "purchase_order_number",
        ]

        corr_col1, corr_col2 = st.columns(2)
        with corr_col1:
            field_to_correct = st.selectbox("Field to Correct:", all_fields)
            current_raw_val = record.raw_fields.get(field_to_correct)
            st.caption(f"Current Value: `{current_raw_val}`")

        with corr_col2:
            proposed_val_str = st.text_input("Proposed Value:", value=str(current_raw_val or ""))

        corr_reason = st.text_input(
            "Correction Rationale (Mandatory, min 3 chars):",
            placeholder="e.g. Corrected invoice total based on verified line-item sum...",
        )

        corr_c1, corr_c2 = st.columns(2)
        with corr_c1:
            is_manual_entry = st.checkbox(
                "Reviewer-Supplied (No source document bounding box exists)",
                value=record.evidence.get(field_to_correct) is None,
                help="Marks the value as reviewer-entered without fabricating coordinates.",
            )
        with corr_c2:
            auto_accept_corr = st.checkbox("Auto-Accept Correction Proposal", value=True)

        if st.button("Submit Field Correction", type="primary"):
            try:
                # Type conversion for decimal fields
                val_to_submit: Any = proposed_val_str
                if field_to_correct in {
                    "total",
                    "subtotal",
                    "tax",
                    "shipping_amount",
                    "discount_amount",
                }:
                    val_to_submit = Decimal(
                        proposed_val_str.replace("$", "").replace(",", "").strip()
                    )

                new_corr = app_state.review_service.submit_correction(
                    review_id=review.review_id,
                    field_name=field_to_correct,
                    corrected_value=val_to_submit,
                    reason=corr_reason,
                    reviewer="reviewer_ap",
                    evidence_references=[field_to_correct]
                    if not is_manual_entry and field_to_correct in record.evidence
                    else [],
                    is_reviewer_supplied=is_manual_entry,
                    auto_accept=auto_accept_corr,
                )
                app_state.save_to_disk()
                st.success(
                    f"Correction `{new_corr.correction_id}` submitted for `{field_to_correct}`!"
                )
                st.rerun()
            except (InvalidCorrectionError, Exception) as exc:
                st.error(f"Correction Rejected: {exc}")

        # List existing corrections
        if review.corrections:
            st.markdown("---")
            st.markdown("##### Existing Field Corrections")
            for _c_idx, c in enumerate(review.corrections):
                c_status = c.status.value
                s_icon = (
                    "✅" if c_status == "ACCEPTED" else ("❌" if c_status == "REJECTED" else "⏳")
                )

                with st.container(border=True):
                    c_col_a, c_col_b, c_col_c = st.columns([3, 2, 2])
                    with c_col_a:
                        st.markdown(
                            f"**{c.field_name}:** `{c.original_value}` ➔ **`{c.corrected_value}`**"
                        )
                        st.caption(f"Reason: {c.reason} | Author: {c.reviewer}")
                    with c_col_b:
                        st.write(f"Status: **{s_icon} {c_status}**")
                        if c.is_reviewer_supplied:
                            st.caption("*(Reviewer-Supplied)*")
                    with c_col_c:
                        if c.status == CorrectionStatus.PROPOSED:
                            btn_acc, btn_rej = st.columns(2)
                            with btn_acc:
                                if st.button("Accept", key=f"acc_{c.correction_id}"):
                                    app_state.review_service.accept_correction(
                                        review.review_id, c.correction_id, reviewer="reviewer_ap"
                                    )
                                    app_state.save_to_disk()
                                    st.rerun()
                            with btn_rej:
                                if st.button("Reject", key=f"rej_{c.correction_id}"):
                                    app_state.review_service.reject_correction(
                                        review.review_id,
                                        c.correction_id,
                                        reviewer="reviewer_ap",
                                        rejection_reason="Rejected by reviewer",
                                    )
                                    app_state.save_to_disk()
                                    st.rerun()

    # -------------------------------------------------------------------------
    # TAB 4: Review Decisions & Verification Gateways
    # -------------------------------------------------------------------------
    with tab_decision:
        st.markdown("##### ⚖️ Review Decision & Approval Gateways")

        current_review_status = review.status.value
        st.write(f"Current State: **`{current_review_status}`** (Revision: `v{review.revision}`)")

        # Evaluate effective validation status
        effective_val = (
            review.corrected_view.corrected_validation_result
            if review.corrected_view and review.corrected_view.corrected_validation_result
            else initial_val
        )
        is_invalid = effective_val.overall_status == OverallValidationStatus.INVALID
        is_needs_review = effective_val.overall_status == OverallValidationStatus.NEEDS_REVIEW
        is_valid = effective_val.overall_status in {
            OverallValidationStatus.VALID,
            OverallValidationStatus.VALID_WITH_WARNINGS,
        }

        # Lifecycle Controls
        c_dec1, c_dec2 = st.columns(2)

        with c_dec1:
            if review.status == ReviewStatus.PENDING:
                if st.button(
                    "▶️ Start Inspection (Claim Review)", type="primary", use_container_width=True
                ):
                    try:
                        app_state.review_service.start_review(
                            review.review_id, reviewer="reviewer_ap"
                        )
                        app_state.save_to_disk()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            elif review.status in {
                ReviewStatus.IN_REVIEW,
                ReviewStatus.CORRECTION_REQUESTED,
                ReviewStatus.RETURNED_FOR_REVIEW,
            }:
                # Approval Gateway checks
                approval_disabled = is_invalid
                blocking_msg = ""
                if is_invalid:
                    blocking_msg = "🚫 Approval Blocked: Missing mandatory fields. Must accept corrections for missing fields before approval."

                override_reason_needed = is_needs_review
                approval_reason_code = "APPROVED_VERIFIED"
                if override_reason_needed:
                    st.warning(
                        "⚠️ High-severity discrepancies remain. Approval requires an authorized override code:"
                    )
                    approval_reason_code = st.selectbox(
                        "Override Reason Code:",
                        [
                            "OVERRIDE_FINANCE_APPROVED",
                            "OVERRIDE_CONTRACTUAL_VARIANCE",
                            "OVERRIDE_DISPUTE_SETTLED",
                        ],
                    )

                approval_comment = st.text_input(
                    "Approval Comment (Optional):", placeholder="Verified against PO..."
                )

                if approval_disabled:
                    st.error(blocking_msg)
                    st.button("✅ Approve Invoice", disabled=True, use_container_width=True)
                else:
                    if st.button("✅ Approve Invoice", type="primary", use_container_width=True):
                        try:
                            app_state.review_service.approve_document(
                                review.review_id,
                                reviewer="reviewer_ap",
                                reason_code=approval_reason_code,
                                comment=approval_comment,
                            )
                            app_state.save_to_disk()
                            st.success("Invoice successfully approved!")
                            st.rerun()
                        except (
                            UnresolvedDiscrepancyError,
                            ReviewConcurrencyError,
                            Exception,
                        ) as exc:
                            st.error(f"Approval Gateway Error: {exc}")

        with c_dec2:
            if review.status in {
                ReviewStatus.IN_REVIEW,
                ReviewStatus.PENDING,
                ReviewStatus.CORRECTION_REQUESTED,
                ReviewStatus.RETURNED_FOR_REVIEW,
            }:
                with st.expander("🚫 Reject Document"):
                    rej_reason_code = st.selectbox(
                        "Rejection Reason Code:",
                        [
                            "REJECTED_ARITHMETIC_ERROR",
                            "REJECTED_MISSING_DATA",
                            "REJECTED_DUPLICATE",
                            "REJECTED_FRAUDULENT",
                        ],
                    )
                    rej_comment = st.text_area("Rejection Rationale (Mandatory):")
                    if st.button("Confirm Rejection", type="secondary", use_container_width=True):
                        if not rej_comment.strip():
                            st.error("A non-empty rejection comment is required.")
                        else:
                            app_state.review_service.reject_document(
                                review.review_id,
                                reviewer="reviewer_ap",
                                reason_code=rej_reason_code,
                                comment=rej_comment,
                            )
                            app_state.save_to_disk()
                            st.success("Document rejected.")
                            st.rerun()

            elif review.status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
                st.info(f"Document has reached terminal state **{review.status.value}**.")
                rereview_reason = st.text_input(
                    "Reason for Re-Review:", placeholder="Audit compliance sweep..."
                )
                if st.button("🔄 Return for Re-Review", use_container_width=True):
                    if not rereview_reason.strip():
                        st.error("Please supply a reason for re-opening review.")
                    else:
                        app_state.review_service.return_for_review(
                            review.review_id, reviewer="reviewer_lead", reason=rereview_reason
                        )
                        app_state.save_to_disk()
                        st.rerun()
