# DocuMind User & Operator Guide

DocuMind is an intelligent, auditable document extraction and verification system engineered for high-accuracy processing of financial documents, with an initial focus on **invoices**.

This guide covers everything required to install, configure, operate, review, and export invoices using DocuMind.

---

## 1. Environment Setup & Installation

### 1.1 Prerequisites
- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Version 3.10, 3.11, or 3.12 (Python 3.12 recommended).
- **OCR Engine (Optional for Scanned Documents)**: [Tesseract OCR 5.x](https://github.com/UB-Mannheim/tesseract/wiki).
  - Digital vector PDFs process with 100% fidelity without Tesseract.
  - Scanned/image-only PDFs use Tesseract as an automated OCR fallback.

### 1.2 Virtual Environment & Package Installation
Open Windows PowerShell or a command shell:

```powershell
# Clone or navigate to the repository
cd "D:\Project\Intelligent Document Extraction"

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# Install editable package with all dependencies
pip install -e ".[dev]"
```

### 1.3 Configuration (`.env`)
Copy the environment template if not already present:
```powershell
cp .env.example .env
```

Ensure `.env` contains:
```env
DOCUMIND_ENV=development
DOCUMIND_DEBUG=true
DOCUMIND_LOG_LEVEL=INFO
DOCUMIND_LOG_PII=false
DOCUMIND_TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Verify Tesseract path:
```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

---

## 2. Launching the Streamlit Application

Start the application using the Streamlit CLI:

```powershell
streamlit run app/Home.py
```

The application will start and provide a local URL:
```text
  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```
Open your modern web browser (Chrome, Edge, Firefox) to `http://localhost:8501`.

---

## 3. Application Tour & Workflow

DocuMind is organized as a multipage Streamlit application accessible via the left sidebar.

```text
app/
├── Home.py                  # Entry hub, health checks, quickstart
└── pages/
    ├── 01_Dashboard.py          # Operational metrics, discrepancy trends, queues
    ├── 02_Upload_Invoices.py    # Multi-file secure upload, validation, extraction
    ├── 03_Document_Explorer.py  # Filterable invoice registry & search
    ├── 04_Review_Workbench.py   # Side-by-side PDF evidence viewer & review editor
    ├── 05_Validation_Reports.py # Business rule hit rates & discrepancy drilldowns
    ├── 06_Audit_History.py      # Immutable event stream & actor attribution
    └── 07_Settings.py           # Configuration diagnostics, corpus loader, batch exports
```

---

### Page 0: Home (`Home.py`)
- **System Diagnostics**: Live status indicators verifying Python version, PyMuPDF engine, Tesseract OCR executable, and storage health.
- **Quick Pipeline Overview**: Architecture summary outlining the 5-stage pipeline: Secure Ingestion $\to$ Hybrid Text Extraction $\to$ Structured Field Extraction $\to$ Business Rule Validation $\to$ Human Review & Audit.
- **Corpus Quickstart**: Direct button to preload 10 sample synthetic invoices to immediately explore the system without manual uploads.

---

### Page 1: Operational Dashboard (`01_Dashboard.py`)
- **Key Performance Indicators (KPIs)**:
  - Total Ingested Invoices.
  - Review Status Breakdown (`VALID`, `NEEDS_REVIEW`, `FLAGGED`, `APPROVED`, `REJECTED`).
  - Total Discrepancy Count across the active batch.
  - Straight-Through Processing (STP) rate (%) — invoices requiring zero human intervention.
- **Discrepancy Analytics**: Severity distribution (`CRITICAL`, `WARNING`, `INFO`) and category breakdowns (`ARITH`, `BIZ`, `DUP`, `REF`).
- **Recent Ingestion Activity**: Live table of recently processed invoices with one-click navigation links to the Review Workbench.

---

### Page 2: Secure Invoice Upload (`02_Upload_Invoices.py`)
- **Upload Portal**: Accepts single or multiple PDF documents (`.pdf`).
- **Multi-Gate Validation Engine**:
  - Size validation (rejects files exceeding 25 MB).
  - Magic byte verification (`%PDF-` signature check).
  - Parser structure check (verifies PyMuPDF can open the document).
  - Password/encryption rejection (encrypted PDFs are blocked safely).
  - Duplicate payload detection via SHA-256 fingerprinting (prevents duplicate storage).
- **Automated Pipeline Processing**:
  - Immediately executes hybrid extraction (native text + OCR fallback).
  - Performs rule-based structured extraction and field evidence mapping.
  - Executes Phase 5 business validation rules.
  - Registers the document in the human review queue.

---

### Page 3: Document Explorer (`03_Document_Explorer.py`)
- **Search & Filters**:
  - Search by Invoice Number, Vendor Name, or Document ID.
  - Filter by Review Status (`NEEDS_REVIEW`, `VALID`, `APPROVED`, etc.).
  - Filter by Ingestion Date range.
- **Visual Status Badges**:
  - Clear visual chips indicating invoice status, extraction confidence, and discrepancy counts.
  - Highlights missing or ambiguous fields with warning indicators.
- **Document Detail Drawer**:
  - Quick inspection of header metadata, financial totals, line item count, and validation summary without leaving the explorer.
  - Direct deep-link button opening the document in the Review Workbench.

---

### Page 4: Interactive Review Workbench (`04_Review_Workbench.py`)
The centerpiece of the DocuMind human review process, featuring a side-by-side interface:

#### Left Pane: High-Resolution PDF Evidence Viewer
- **Crisp Page Rendering**: High-DPI rasterization of the original PDF document.
- **Live Bounding-Box Overlays**:
  - Select any extracted field in the right panel to highlight its exact physical bounding box on the PDF.
  - Rendered with translucent amber highlight overlays and token boundary tags.
  - Automatically identifies whether evidence stems from native vector text or OCR recognition.
  - If a field is missing, ambiguous, or manually entered, a clear badge explains why no bounding box exists.

#### Right Pane: Field Editor, Discrepancies & Approval Gateways
- **Discrepancy Navigator**:
  - Lists all active discrepancies categorized by severity (`CRITICAL`, `WARNING`, `INFO`).
  - Displays rule IDs (e.g. `ARITH_TOTAL_MISMATCH`, `BIZ_MISSING_INVOICE_NUMBER`), expected values, and observed values.
- **Extracted Fields & Proposed Corrections**:
  - Inspect Vendor Name, Invoice Number, Issue Date, Due Date, Subtotal, Tax Amount, and Total Amount.
  - **Non-Destructive Corrections**: Reviewers can propose corrections to any field with mandatory justification notes.
  - Corrected values are tagged with `is_reviewer_supplied=True` and tracked in the audit log; the original extracted text and evidence coordinates are strictly preserved.
- **Strict Approval Gateways**:
  - **Approval Blockers**: Invoices with `CRITICAL` discrepancies (e.g. missing mandatory invoice number or vendor name) cannot be approved until corrected.
  - **Override Controls**: Warnings (such as arithmetic differences under tolerance) require an explicit override reason to approve.
  - **Rejection Portal**: Allows rejecting non-compliant or fraudulent documents with mandatory rejection rationale.
  - **Revision Locking**: Optimistic concurrency control (`revision_id`) prevents overwriting concurrent edits. Once `APPROVED` or `REJECTED`, fields are locked from further editing.

---

### Page 5: Validation Reports (`05_Validation_Reports.py`)
- **Rule Catalogue Compliance**: Hit rates across all validation rules:
  - `ARITH`: Arithmetic checks (Line item sums, Subtotal + Tax = Total, Discount calculations).
  - `BIZ`: Business rules (Issue date $\le$ Due date, Future date thresholds, Mandatory field presence).
  - `DUP`: Duplicate detection (Duplicate invoice number for same vendor).
  - `REF`: Reference reconciliation (Known vendor catalogue verification).
- **Detailed Discrepancy Registry**: Filterable table of all discrepancies across the portfolio with document links and remediation status.

---

### Page 6: Audit History (`06_Audit_History.py`)
- **Immutable Event Stream**: Chronological ledger of all lifecycle events:
  - Document ingestion and SHA-256 fingerprint generation.
  - Extraction and validation completion.
  - Field correction proposals and acceptances.
  - Review decisions (approval, rejection, reset).
- **Actor Attribution**: Tracks who performed each action (reviewer username/ID, timestamp, and client IP or system identifier).
- **Payload Inspection**: Expandable granular JSON view of before-and-after states for every audit event.

---

### Page 7: Settings & Batch Export (`07_Settings.py`)
- **Environment Diagnostics**: Live inspection of current settings, storage directories, and Tesseract configuration.
- **Corpus Ingestion Utilities**:
  - **Load 10 Sample Invoices**: Fast loader for demonstration and quick testing.
  - **Load All 50 Synthetic Invoices**: Full batch loader for evaluation across all 30 digital and 20 scanned test documents.
- **Export & Reporting Hub**:
  - Export **Processing Summary** (CSV & JSON).
  - Export **Validation Discrepancies** (CSV & JSON).
  - Export **Review Outcomes** (CSV & JSON).
  - Export **Correction History** (CSV & JSON).
  - Export **Full Audit Trail** (CSV & JSON).
- **CSV Formula-Injection Protection**: All CSV exports sanitize untrusted inputs by automatically prefixing dangerous trigger characters (`=`, `+`, `-`, `@`, `\t`, `\r`, `%`) with a single quote (`'`), protecting downstream Microsoft Excel users against formula injection exploits (CWE-1236).

---

## 4. Verification & Testing

DocuMind includes a comprehensive automated test suite and evaluation script:

```powershell
# Run full pytest test suite (175+ tests) with coverage
pytest -v --cov=src/documind --cov-report=term-missing

# Run extraction & business validation benchmark across the 50-document corpus
python scripts/evaluate_extraction.py

# Run empirical performance benchmark
python scripts/benchmark_performance.py

# Run code style & formatting checks
ruff check .
ruff format --check .
```

---

## 5. Security, Persistence & Privacy Notes

- **Local Processing**: All PDF extraction, OCR processing, and business validations occur 100% locally on the host machine. No documents or extracted texts are transmitted to external cloud APIs.
- **PII-Safe Logging**: Structured logging automatically redacts sensitive financial figures and personal identifiers unless `DOCUMIND_LOG_PII=true` is explicitly enabled for development.
- **File System Isolation**: Uploaded documents are saved under isolated UUID directories with strict traversal checks.
- **Atomic State Persistence**: Application state is saved atomically via `.tmp` files and `os.replace`. If an interrupted write or corrupted snapshot is detected, DocuMind creates a `.corrupted_<timestamp>` backup for forensic inspection and initializes safely without crashing.
- **Formula-Injection Defense (CWE-1236)**: All tabular CSV exports automatically neutralize executable expressions by prepending single quotes to leading trigger characters.

