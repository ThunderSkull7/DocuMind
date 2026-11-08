# DocuMind — Intelligent Document Extraction & Verification System

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture: Modular Monolith](https://img.shields.io/badge/Architecture-Modular%20Monolith-orange.svg)](#4-architecture-overview)
[![Phase](https://img.shields.io/badge/Phase-8%20Technical%20Audit%20%26%20Publication%20Ready-success.svg)](#8-development-status)
[![CI](https://github.com/documind/documind/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-160%2B%20Passed-brightgreen.svg)](#6-running-tests--quality-checks)
[![Coverage](https://img.shields.io/badge/Coverage-89%25-brightgreen.svg)](#6-running-tests--quality-checks)

DocuMind is an intelligent, auditable document extraction and verification system engineered for high-accuracy processing of financial documents, with an initial core focus on **invoices**.

---

## 1. Problem Statement

Organizations process thousands of invoices annually in heterogeneous formats—ranging from native digital PDFs with selectable text to poorly scanned, skewed image documents. Traditional Optical Character Recognition (OCR) systems and basic regex parsers frequently suffer from:
- Fragile extraction logic that breaks upon minor layout changes.
- Inability to handle digital and scanned documents seamlessly.
- Lack of auditability and missing spatial evidence (provenance).
- High error rates in arithmetic totals and date discrepancies.
- Privacy risks associated with sending confidential financial documents to unverified cloud APIs.

DocuMind addresses these challenges with a modular pipeline combining local native PDF parsing, offline OCR fallback, rigorous Pydantic-based schema and arithmetic validation, coordinate-grounded evidence tracking, an interactive human review workbench, and formula-injection-safe reporting.

---

## 2. Implemented Subsystems (Phases 1 – 8)

### 2.1 Comprehensive Audit, Hardening & Publication Readiness (Phase 8)
- **Technical & Security Audit**: Evaluated against CWE-22 (Path Traversal), CWE-1236 (CSV Formula Injection), and DoS boundaries.
- **Persistence Hardening**: Atomic JSON file writes (`.tmp` + `os.replace`) and corrupted snapshot recovery backing up malformed files to `.corrupted_<timestamp>`.
- **Property-Based Invariants**: Invariant tests validating IEEE-754 float drift immunity via `Decimal`, coordinate containment across arbitrary DPI, and date ambiguity detection.
- **Publication Readiness**: Full documentation and reports establishing Level 1 (GitHub) and Level 2 (Local Demo) publication readiness.

### 2.2 Multipage Streamlit Application & Review Workbench (Phase 7)
- **Interactive Review Workbench**: High-resolution PDF rasterization with dynamic, scaled bounding-box overlays (`rgba(245, 158, 11, 0.25)`). Textual fallback banners for missing or reviewer-supplied fields prevent coordinate hallucinations.
- **Strict Verification Gateways**: Enforces non-destructive correction workflows; blocks approval of invalid invoices with critical discrepancies.
- **Operational Dashboards & Compliance Reports**: Live AP metrics, straight-through processing rates, and rule catalogue hit rates (`ARITH`, `BIZ`, `DUP`, `REF`).
- **CWE-1236 Formula-Injection Defense**: Tabular CSV exports sanitize untrusted inputs by automatically prefixing dangerous trigger characters (`=`, `+`, `-`, `@`, `\t`, `\r`, `%`) with a single quote (`'`).

### 2.3 Human Review Workflow & Audit Trail (Phase 6)
- **Deterministic State Machine**: Manages invoice review states (`PENDING`, `IN_REVIEW`, `CORRECTION_REQUESTED`, `APPROVED`, `REJECTED`, `RETURNED_FOR_REVIEW`).
- **Non-Destructive Field Corrections**: Field edits create distinct correction records while preserving original extraction records and bounding boxes.
- **Append-Only Audit Trail**: Immutable sequence of timestamped events with actor attribution.

### 2.4 Deterministic Business Validation & Discrepancies (Phase 5)
- **Arithmetic Consistency**: Fixed-point `Decimal` math verifying line-item sums and total calculations ($S + T = T$).
- **Business Rule Integrity**: Completeness, future date caps, and ambiguous date formatting checks.
- **Duplicate Detection**: Multi-tier detection for exact file hashes, vendor/invoice ID collisions, and potential duplicates.

### 2.5 Structured Invoice Field Extraction & Evidence Mapping (Phase 4)
- **Rule-Based Extraction**: Deterministic extraction of header metadata, financial amounts, and tabular line items.
- **Coordinate Grounding**: Every extracted field is mapped to physical PDF coordinates (`[x0, y0, x1, y1]`) in standard PDF points.

### 2.6 Hybrid PDF Text Extraction & OCR Fallback (Phases 3 & 3.1)
- **High-Fidelity Native PDF Extraction**: PyMuPDF-based text and bounding box extraction.
- **Page-Level Hybrid Routing**: Digital pages route to native extraction; image pages route to local Tesseract OCR.
- **Engine Confidence Provenance**: Native vector text records `confidence = None`; OCR tokens record raw engine confidence scores.

### 2.7 Secure Ingestion Subsystem & Synthetic Corpus (Phase 2)
- **Deep File Validation**: Header inspection, size capping (25MB), parser integrity, encryption rejection.
- **Synthetic Benchmark Corpus**: 50 synthetic invoices (30 digital + 20 scanned) with 5 layout templates and gold-standard annotations.

---

## 3. Technology Stack

- **Core Runtime**: Python 3.10 – 3.12 (Python 3.12 recommended)
- **PDF Processing**: `pymupdf` (MuPDF C-engine bindings)
- **Image Processing**: `Pillow` (PIL)
- **OCR Engine**: `pytesseract` + local Tesseract OCR binary (v5.4.0)
- **Data Validation & Typing**: `pydantic` v2, `pydantic-settings`
- **User Interface**: `streamlit`
- **Testing & Quality**: `pytest`, `pytest-cov`, `ruff`

---

## 4. Architecture Overview

```text
src/documind/
├── config.py             # Centralized configuration & dynamic paths
├── logging.py            # PII-safe structured logging
├── exceptions.py         # Unified exception hierarchy
├── dataset/              # Synthetic corpus generation & manifest models
├── ingestion/            # Multi-gated validation, atomic storage & service
├── extraction/           # Hybrid PDF text, OCR fallback, structured extractors & evidence
├── schemas/              # Pydantic models for invoices & evidence
├── validation/           # Schema, arithmetic & duplicate rule validators
├── review/               # Review state machine, corrections & append-only audit trail
└── reporting/            # CSV & JSON export generators with CWE-1236 sanitization

app/
├── Home.py               # Landing page, system diagnostics & quickstart
├── components/           # Reusable PDF viewer with bounding-box highlights
├── services/             # Singleton state management & atomic JSON persistence
└── pages/
    ├── 01_Dashboard.py          # Operational AP dashboard & discrepancy trends
    ├── 02_Upload_Invoices.py    # Multi-file secure upload & processing portal
    ├── 03_Document_Explorer.py  # Filterable invoice registry with detail drawers
    ├── 04_Review_Workbench.py   # Side-by-side PDF evidence viewer & review editor
    ├── 05_Validation_Reports.py # Business rule catalogue hit rates
    ├── 06_Audit_History.py      # Immutable event stream & actor attribution
    └── 07_Settings.py           # Environment diagnostics, corpus loader, batch exports
```

For comprehensive architectural details, consult [`docs/architecture.md`](docs/architecture.md), [`docs/user_guide.md`](docs/user_guide.md), and [`docs/decisions/`](docs/decisions/).

---

## 5. Performance Benchmark Summary

Empirical benchmarks measured across all 50 synthetic corpus documents on Windows 11 (64-bit), Python 3.12.10, Tesseract OCR 5.4.0:

| Metric / Stage | Digital Invoices (30 docs) | Scanned Invoices (20 docs) | Notes |
| :--- | :---: | :---: | :--- |
| **Text Extraction / OCR** | 28.58 ms (mean) | 999.71 ms (mean) | Native C-parsing vs local Tesseract |
| **Structured Field Extraction** | 4.56 ms (mean) | 4.89 ms (mean) | Regex & spatial clustering |
| **Business Rule Validation** | 0.27 ms (mean) | 0.30 ms (mean) | Fixed-point `Decimal` checks |
| **End-to-End Processing Latency** | **33.41 ms** (mean) | **1004.90 ms** (mean) | **30 docs/sec** (digital) vs **1 s/doc** (scanned) |
| **Peak Memory Consumption** | **2.22 MB** | **2.22 MB** | Traced above baseline memory |
| **Total Batch Time (50 docs)** | — | — | **21.11 seconds** wall duration |

---

## 6. Installation & Getting Started

### 6.1 Clone & Setup (Windows PowerShell)
```powershell
# Navigate to the repository
cd "D:\Project\Intelligent Document Extraction"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install editable package with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### 6.2 OCR Configuration (Optional for Scanned Documents)
To enable live OCR recognition on scanned/image-based PDFs:
1. Install [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki).
2. Set `DOCUMIND_TESSERACT_CMD` in `.env`:
   ```bash
   DOCUMIND_TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

### 6.3 Launch the Streamlit Web Application
```powershell
streamlit run app/Home.py
```
Open your browser at `http://localhost:8501`.

---

## 7. Running Tests & Quality Checks

Run the automated test suite with coverage:
```powershell
pytest -v --cov=src/documind --cov-report=term-missing
```

Run linter and formatting checks:
```powershell
ruff check .
ruff format --check .
```

Run extraction and business validation benchmark across all 50 corpus documents:
```powershell
python scripts/evaluate_extraction.py
```

Run performance benchmarking script:
```powershell
python scripts/benchmark_performance.py
```

---

## 8. Operational Readiness Assessment

| Readiness Level | Status | Scope |
| :--- | :---: | :--- |
| **Level 1: Ready for GitHub Publication** | **READY** | Clean tree, complete docs, MIT license, zero secrets, 100% reproducible. |
| **Level 2: Ready for Local Demonstration** | **READY** | Streamlit app launches, 10-sample one-click loader, interactive review workbench. |
| **Level 3: Ready for Controlled Pilot Use** | **CONDITIONAL** | Workstation AP analysts processing small batches (<200 docs/day). |
| **Level 4: Ready for Public Cloud Deployment** | **NOT READY** | Requires migrating state to PostgreSQL, S3 storage, and auth/RBAC. |
| **Level 5: Ready for Enterprise Production** | **NOT READY** | Requires containerized PDF sandboxing, Celery queues, and ERP integration. |

For detailed audit assessments, consult:
- [`reports/DOCUMIND_FINAL_TECHNICAL_AUDIT.md`](reports/DOCUMIND_FINAL_TECHNICAL_AUDIT.md)
- [`reports/DOCUMIND_FINAL_EVALUATION.md`](reports/DOCUMIND_FINAL_EVALUATION.md)
- [`reports/DOCUMIND_SECURITY_REVIEW.md`](reports/DOCUMIND_SECURITY_REVIEW.md)
- [`reports/DOCUMIND_PUBLICATION_READINESS.md`](reports/DOCUMIND_PUBLICATION_READINESS.md)

---

## 9. Development Status

| Phase | Milestone | Status |
| :---: | :--- | :---: |
| **Phase 1** | **Project Foundation, Scope & Architecture** | **Completed** |
| **Phase 2** | **Synthetic Invoice Dataset & Secure Ingestion** | **Completed** |
| **Phase 3** | **Hybrid PDF Text Extraction & OCR Pipeline** | **Completed** |
| **Phase 3.1** | **OCR Verification & Test Failure Closure** | **Completed** |
| **Phase 4** | **Structured Invoice Field Extraction & Evidence Mapping** | **Completed** |
| **Phase 5** | **Business Rule Validation, Arithmetic Consistency & Discrepancies** | **Completed** |
| **Phase 6** | **Human Review Workflow & Audit Trail** | **Completed** |
| **Phase 7** | **Streamlit Application, Interactive Review & Reporting** | **Completed** |
| **Phase 8** | **Comprehensive Technical Audit, Security Hardening & Publication Readiness** | **Completed** |

---

## 10. License

This project is licensed under the MIT License - see the LICENSE file for details.
