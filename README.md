# DocuMind — Intelligent Document Extraction & Verification System

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture: Modular Monolith](https://img.shields.io/badge/Architecture-Modular%20Monolith-orange.svg)](#architecture)
[![Phase](https://img.shields.io/badge/Phase-1%20Foundation-yellow.svg)](#development-status)

DocuMind is an intelligent, auditable document extraction and verification system engineered for high-accuracy processing of financial documents, with an initial core focus on **invoices**.

---

## 1. Problem Statement

Organizations process thousands of invoices annually in heterogeneous formats—ranging from native digital PDFs with selectable text to poorly scanned, skewed image documents. Traditional Optical Character Recognition (OCR) systems and basic regex parsers frequently suffer from:
- Fragile extraction logic that breaks upon minor layout changes.
- Inability to handle digital and scanned documents seamlessly.
- Lack of auditability and missing spatial evidence (provenance).
- High error rates in arithmetic totals and date discrepancies.
- Privacy risks associated with sending confidential financial documents to unverified cloud APIs.

DocuMind addresses these challenges with a modular pipeline combining local native PDF parsing, offline OCR fallback, rigorous Pydantic-based schema and arithmetic validation, coordinate-grounded evidence tracking, and a human-in-the-loop verification workflow.

---

## 2. Core Functionality (Roadmap)

- **Dual-Engine Ingestion & Extraction**: Native digital PDF text extraction via PyMuPDF with automatic fallback to Tesseract OCR for scanned or flattened documents.
- **Strict Invoice Field Extraction**: Structured extraction covering:
  - `invoice_number`
  - `invoice_date`
  - `vendor_name`
  - `currency`
  - `subtotal`
  - `tax`
  - `total`
- **Spatial Grounding & Evidence Tracking**: Bounding boxes, page coordinates, raw text segments, and extraction confidence attached to each field.
- **Two-Tier Validation**:
  - *Schema Validation*: Type safety, mandatory fields, date format adherence.
  - *Business Rules Validation*: Arithmetic integrity ($\text{subtotal} + \text{tax} = \text{total}$), temporal checks, currency verification.
- **Human-in-the-Loop Review**: Streamlit-based interface highlighting evidence directly on PDF previews, enabling one-click approvals and auditable overrides.
- **Export & Integration**: Exporting approved, verified records to standardized CSV and JSON formats.

---

## 3. Technology Stack

- **Core Runtime**: Python 3.10 – 3.12
- **PDF Processing**: `pymupdf` (MuPDF C-engine bindings)
- **OCR Engine**: `pytesseract` + local Tesseract OCR
- **Data Validation & Typing**: `pydantic` v2, `pydantic-settings`
- **User Interface**: `streamlit`
- **Data Processing**: `pandas`, `Pillow`
- **Testing & Quality**: `pytest`, `pytest-cov`, `ruff`

---

## 4. Architecture Overview

DocuMind follows a clean, modular monolith design organized by domain capabilities:

```text
src/documind/
├── config.py         # Centralized configuration & dynamic paths
├── logging.py        # PII-safe structured logging
├── exceptions.py     # Unified exception hierarchy
├── ingestion/        # Upload validation & isolated storage
├── extraction/       # Native PDF text & OCR fallback extractors
├── schemas/          # Pydantic models for invoices & evidence
├── validation/       # Schema & arithmetic business rule validators
├── matching/         # Reference-record reconciliation
├── review/           # State management & human review audits
└── reporting/        # CSV and JSON export generators
```

For comprehensive architectural details, data flow diagrams, and design rationales, consult [`docs/architecture.md`](docs/architecture.md).

---

## 5. Installation & Getting Started

### 5.1 Prerequisites
- Python 3.10 or higher installed.
- (Optional, for scanned PDF OCR): [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed on your system.

### 5.2 Clone & Install
```bash
# Clone the repository
git clone <repository-url>
cd "Intelligent Document Extraction"

# Create and activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install package in editable mode with development dependencies
pip install -e ".[dev]"
```

### 5.3 Configuration
Copy the configuration template:
```bash
cp .env.example .env
```
Adjust parameters in `.env` if needed (e.g. `DOCUMIND_LOG_LEVEL=DEBUG` or explicit `DOCUMIND_TESSERACT_CMD` path).

### 5.4 Launching the Streamlit Application
```bash
streamlit run app/Home.py
```
Open your browser at `http://localhost:8501`.

---

## 6. Running Tests & Quality Checks

Run the automated test suite:
```bash
pytest
```

Run linter and formatting checks with Ruff:
```bash
ruff check .
ruff format --check .
```

---

## 7. Development Status

| Phase | Milestone | Status |
| :---: | :--- | :---: |
| **Phase 1** | **Project Foundation, Scope & Architecture** | **Completed** |
| Phase 2 | Synthetic Invoice Dataset & Secure Ingestion | Scheduled |
| Phase 3 | Native Extraction & OCR Fallback Pipeline | Scheduled |
| Phase 4 | Schema & Business Rules Validation | Scheduled |
| Phase 5 | Human Review Workflow & Evidence UI | Scheduled |
| Phase 6 | Structured Export & Comprehensive Evaluation | Scheduled |

---

## 8. License

This project is licensed under the MIT License - see the LICENSE file for details.
