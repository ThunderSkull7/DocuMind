"""Audit History & Event Stream page for DocuMind.

Displays the chronological, append-only audit event trail tracking document reviews,
corrections, state transitions, reviewer attribution, and verification decisions.
"""

import pandas as pd
import streamlit as st
from app.services.state import get_app_state

st.set_page_config(
    page_title="Audit History - DocuMind",
    page_icon="📜",
    layout="wide",
)

st.title("📜 Audit History & Compliance Stream")
st.caption(
    "Chronological, append-only audit log tracking every user action, assignment, field correction, "
    "and approval decision with actor attribution and UTC timestamps."
)

st.info(
    "🛡️ **Integrity Notice**: Audit events are strictly append-only. Application interfaces do not permit "
    "editing, updating, or deleting historical events. Any correction requires appending a subsequent explanatory event."
)

app_state = get_app_state()
events = app_state.audit_trail.get_events()

if not events:
    st.info(
        "ℹ️ No audit events recorded yet. Perform review actions or ingest invoices to generate audit entries."
    )
    st.stop()

# Filters Row
f_c1, f_c2, f_c3 = st.columns(3)

with f_c1:
    doc_ids = ["All"] + sorted({e.document_id for e in events})
    filter_doc = st.selectbox("Filter by Document ID:", doc_ids)

with f_c2:
    event_types = ["All"] + sorted({e.event_type.value for e in events})
    filter_type = st.selectbox("Filter by Event Type:", event_types)

with f_c3:
    actors = ["All"] + sorted({e.actor for e in events})
    filter_actor = st.selectbox("Filter by Actor:", actors)

# Apply filters
filtered_events = []
for e in reversed(events):
    if filter_doc != "All" and e.document_id != filter_doc:
        continue
    if filter_type != "All" and e.event_type.value != filter_type:
        continue
    if filter_actor != "All" and e.actor != filter_actor:
        continue
    filtered_events.append(e)

st.write(f"Showing **{len(filtered_events)}** of **{len(events)}** audit events")

# Tabular Overview
table_rows = []
for e in filtered_events:
    table_rows.append(
        {
            "Event ID": e.event_id,
            "Timestamp (UTC)": e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "Event Type": e.event_type.value,
            "Document ID": e.document_id,
            "Review ID": e.review_id,
            "Actor": e.actor,
            "Transition": f"{e.previous_state or '—'} ➔ {e.new_state or '—'}",
            "Affected Fields": ", ".join(e.affected_fields) if e.affected_fields else "—",
            "Comment": e.comment or "—",
        }
    )

if table_rows:
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

st.markdown("---")

# Expandable JSON Inspection
st.markdown("### 🔍 Granular Event Payload Inspection")
selected_event_idx = st.selectbox(
    "Select event to view structured payload:",
    range(len(filtered_events)),
    format_func=lambda idx: (
        f"[{filtered_events[idx].timestamp.strftime('%H:%M:%S')}] {filtered_events[idx].event_type.value} — {filtered_events[idx].document_id} ({filtered_events[idx].actor})"
    ),
)

if filtered_events:
    sel_evt = filtered_events[selected_event_idx]
    st.json(sel_evt.model_dump(mode="json"))
