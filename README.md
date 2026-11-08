# DocuMind — Intelligent Document Extraction & Verification System

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture: Modular Monolith](https://img.shields.io/badge/Architecture-Modular%20Monolith-orange.svg)](#architecture)
[![Phase](https://img.shields.io/badge/Phase-2%20Synthetic%20Corpus%20%26%20Ingestion-success.svg)](#development-status)

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

## 2. Implemented Subsystems (Phase 2)

### 2.1 Synthetic Invoice Corpus
- **50 Synthetic Invoices**: 30 digital vector PDFs (native text) + 20 scanned image-based PDFs (no native text layer, resolution 150–300 DPI, skew -2.5° to +1.8°, contrast/compression artifacts).
- **Gold-Standard Annotations**: 50 individual JSON annotations conforming to DocuMind's invoice models in `data/annotations/`.
- **Manifest Catalog**: `data/manifest.json` recording document IDs, hashes, and characteristics.
- **Intentional Edge Cases**: Missing invoice numbers, missing tax, missing vendor names, ambiguous dates, unusual number formatting, similar-looking characters, arithmetic mismatches, duplicate numbers, and scan distortions.

### 2.2 Secure Document Ingestion Subsystem
- **Deep File Validation**:
  - Extension check (`.pdf`).
  - Size check (`0 < size <= 25MB` default, configurable via `DOCUMIND_MAX_UPLOAD_SIZE_MB`).
  - Signature verification (`%PDF-` magic header within initial 1024 bytes).
  - Parser structural validation (PyMuPDF syntax and object integrity).
  - Encryption policy (password-protected PDFs rejected by default).
  - Page ceiling (1 to 50 pages default, configurable via `DOCUMIND_MAX_PAGE_COUNT`).
- **Safe Local Storage**:
  - Independent UUIDv4 internal document IDs.
  - Path traversal defense & filename sanitization.
  - Atomic writes (`.tmp` write followed by `replace`) ensuring zero partially written files.
  - SHA-256 cryptographic verification.
  - Persisted `metadata.json` audit records.
- **Decoupled Service**:
  - `IngestionService` callable from Streamlit, CLI, or future API endpoints.

---

## 3. Technology Stack

- **Core Runtime**: Python 3.10 – 3.12
- **PDF Processing**: `pymupdf` (MuPDF C-engine bindings)
- **Image Processing**: `Pillow` (PIL)
- **OCR Engine**: `pytesseract` + local Tesseract OCR
- **Data Validation & Typing**: `pydantic` v2, `pydantic-settings`
- **User Interface**: `streamlit`
- **Data Processing**: `pandas`, `numpy`
- **Testing & Quality**: `pytest`, `pytest-cov`, `ruff`

---

## 4. Architecture Overview

```text
src/documind/
├── config.py         # Centralized configuration & dynamic paths
├── logging.py        # PII-safe structured logging
├── exceptions.py     # Unified exception hierarchy
├── dataset/          # Synthetic corpus generation & manifest models
├── ingestion/        # Multi-gated validation, atomic storage & service
├── extraction/       # Native PDF text & OCR fallback extractors (Phase 3)
├── schemas/          # Pydantic models for invoices & evidence
├── validation/       # Schema & arithmetic business rule validators (Phase 4)
├── matching/         # Reference-record reconciliation (Future)
├── review/           # State management & human review audits (Phase 5)
└── reporting/        # CSV and JSON export generators (Phase 6)
```

For comprehensive architectural details, consult [`docs/architecture.md`](docs/architecture.md) and [`docs/decisions/0002-ingestion-and-dataset-architecture.md`](docs/decisions/0002-ingestion-and-dataset-architecture.md).

---

## 5. Installation & Getting Started

### 5.1 Clone & Setup
```bash
# Clone the repository
git clone <repository-url>
cd "Intelligent Document Extraction"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install editable package with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### 5.2 Synthetic Dataset Regeneration
```bash
python scripts/generate_synthetic_dataset.py --seed 42
```

### 5.3 Launch Streamlit Application
```bash
streamlit run app/Home.py
```
Open your browser at `http://localhost:8501`.

---

## 6. Running Tests & Quality Checks

Run the automated test suite (39 tests spanning unit and integration tiers):
```bash
pytest -v
```

Run linter and formatting checks:
```bash
ruff check .
ruff format --check .
```

---

## 7. Development Status

| Phase | Milestone | Status |
| :---: | :--- | :---: |
| **Phase 1** | **Project Foundation, Scope & Architecture** | **Completed** |
| **Phase 2** | **Synthetic Invoice Dataset & Secure Ingestion** | **Completed** |
| Phase 3 | Native Extraction & OCR Fallback Pipeline | Scheduled |
| Phase 4 | Schema & Business Rules Validation | Scheduled |
| Phase 5 | Human Review Workflow & Evidence UI | Scheduled |
| Phase 6 | Structured Export & Comprehensive Evaluation | Scheduled |

---

## 8. License

This project is licensed under the MIT License - see the LICENSE file for details.
