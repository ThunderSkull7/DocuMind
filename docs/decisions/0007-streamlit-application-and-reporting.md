# ADR 0007: Streamlit Application Architecture, Evidence Highlighting & Auditable Reporting

## Status
Accepted

## Date
2026-11-08

## Context
With Phases 1–6 complete, DocuMind possesses a robust backend for document ingestion, hybrid text extraction, structured invoice extraction, business validation, human review management, and an append-only audit trail.
Phase 7 requires integrating these capabilities into a complete, responsive, and auditable web user interface along with an auditable reporting subsystem.

Key architectural challenges include:
1. **Streamlit Multi-Page Navigation & State Isolation**: Streamlit scripts re-execute on every user interaction and page switch. A shared state model is required to preserve review decisions, newly uploaded documents, and audit logs without data loss.
2. **Dynamic Spatial Evidence Visualization**: Rendering original PDF documents alongside extracted values with physical bounding-box overlays without coordinate drift or hallucination.
3. **Approval Gateways**: Enforcing strict business logic in the UI so that invalid documents or documents with critical discrepancies cannot be approved accidentally.
4. **Export Safety**: Exporting audit trails, discrepancy reports, and review outcomes to CSV without exposing downstream spreadsheet users to CSV Formula Injection attacks (CWE-1236).

## Decision

### 1. Centralized Application State & JSON Persistence (`app/services/state.py`)
- We introduce `AppState`, a thread-safe singleton holding references to all DocuMind domain services (`IngestionService`, `ExtractionService`, `StructuredInvoiceExtractor`, `ValidationService`, `ReviewService`, `AuditTrail`).
- Review records and audit events are automatically persisted to disk under `data/storage/app_state/` (`reviews.json` and `audit.json`) using atomic writes.
- When documents are uploaded, SHA-256 payload deduplication checks prevent duplicate ingestions and re-link directly to existing records.

### 2. High-DPI Evidence Rendering with Strict Token Coordinate Projection (`app/components/pdf_viewer.py`)
- The PDF viewer component rasterizes the original PDF using PyMuPDF (`fitz.Page.get_pixmap(dpi=150)`).
- Extracted spatial tokens (recorded in standard PDF points $72 \text{ pt} = 1 \text{ inch}$) are converted to render pixel dimensions using explicit scale factors:
  $$s_x = \frac{\text{pixmap.width}}{\text{page.rect.width}}, \quad s_y = \frac{\text{pixmap.height}}{\text{page.rect.height}}$$
- Amber bounding boxes (`rgba(245, 158, 11, 0.25)`) with high-contrast borders and badge labels are dynamically drawn over the image.
- If a field is missing, ambiguous, or manually supplied by a reviewer, the system explicitly displays a textual notification rather than rendering a fabricated or default bounding box.

### 3. Strict Verification Gateways in Review Workbench (`04_Review_Workbench.py`)
- Documents in `INVALID` or `NEEDS_REVIEW` state with critical discrepancies disable the approval gateway.
- Reviewers can propose corrections non-destructively; accepted corrections re-evaluate validation rules and update review status.
- Warnings require an explicit override reason code and rationale before approval can proceed.
- Optimistic locking via `revision_id` ensures concurrent edits cannot silently overwrite reviewer decisions.

### 4. CWE-1236 Formula-Injection Sanitization in Reporting (`src/documind/reporting/`)
- All tabular CSV exports pass every text cell through `sanitize_csv_value()`.
- Any cell beginning with `=`, `+`, `-`, `@`, `\t`, `\r`, or `%` is prefixed with a single quote (`'`), neutralizing executable expressions in Microsoft Excel, LibreOffice Calc, and Google Sheets.
- JSON exports provide raw, unmodified structured data for programmatic consumer pipelines.

## Consequences

### Positive
- Fully cohesive end-to-end user experience integrating all backend capabilities.
- Complete traceability: from pixel/point on a PDF through rule validation to human review and final export.
- Secure by default: protection against formula injection, path traversal, and unauthorized state overrides.

### Limitations
- Single-instance local JSON persistence: Suitable for local evaluation, workstation use, and pilot deployments. Not designed for distributed, multi-tenant concurrent writes. Multi-operator environments will migrate persistence to a relational database in future phases.

