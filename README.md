# DocuMind — Intelligent Document Extraction & Verification System

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture: Modular Monolith](https://img.shields.io/badge/Architecture-Modular%20Monolith-orange.svg)](#architecture)
[![Phase](https://img.shields.io/badge/Phase-3%20Hybrid%20Text%20Extraction%20%26%20OCR-success.svg)](#development-status)

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

## 2. Implemented Subsystems (Phases 1 – 3)

### 2.1 Hybrid PDF Text Extraction Engine (Phase 3)
- **High-Fidelity Native PDF Extraction**: PyMuPDF-based extraction of text blocks, spans, words, reading order, and precise spatial bounding boxes.
- **Page-Level Hybrid Routing**: Assesses character counts, alphanumeric ratios, and text density on every page. Automatically routes digital pages to native extraction and scanned/image pages to OCR fallback.
- **Local Tesseract OCR Integration**: Rasterizes pages to 300 DPI pixmaps in memory and processes via `pytesseract`. Projects raster image coordinates to standard PDF points with top-left origin.
- **Deterministic Text Normalization**: Unifies line endings, strips non-printable control characters, and collapses whitespace while strictly preserving invoice identifiers (e.g. `INV-0O1I1lB8`), decimal separators (dots and commas), and currency symbols.
- **Standardized Coordinate System**: PDF point units (`72 pt = 1 inch`) with origin `(0, 0)` at top-left.
- **Engine Confidence Provenance**: Native vector text explicitly records `confidence = None`; OCR tokens record normalized engine-reported confidence.

### 2.2 Secure Document Ingestion Subsystem (Phase 2)
- **Deep File Validation**: Extension check, size limits (25MB default), `%PDF-` signature inspection, structural parser validation, and encryption policy.
- **Safe Local Storage**: UUIDv4-isolated folders, path traversal defense, atomic writes via `.tmp` file replacement, and SHA-256 fingerprinting.

### 2.3 Synthetic Invoice Corpus (Phase 2)
- **50 Synthetic Invoices**: 30 digital vector PDFs + 20 scanned image-based PDFs with 5 distinct layout templates and deliberate challenging cases (missing numbers, arithmetic mismatches, ambiguous dates).
- **Gold-Standard Annotations**: 50 JSON annotations in `data/annotations/` cataloged in `data/manifest.json`.

---

## 3. Technology Stack

- **Core Runtime**: Python 3.10 – 3.12
- **PDF Processing**: `pymupdf` (MuPDF C-engine bindings)
- **Image Processing**: `Pillow` (PIL)
- **OCR Engine**: `pytesseract` + local Tesseract OCR binary
- **Data Validation & Typing**: `pydantic` v2, `pydantic-settings`
- **User Interface**: `streamlit`
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
├── extraction/       # Native PDF text, OCR fallback & hybrid routing
│   ├── models.py     # Standardized extraction output & spatial tokens
│   ├── pdf_text.py   # PyMuPDF native text & bounding box extractor
│   ├── ocr.py        # Tesseract wrapper & pixel-to-point projector
│   ├── quality.py    # Text density & alphanumeric quality assessor
│   ├── routing.py    # Page-level hybrid router (native vs OCR)
│   ├── normalization.py # Safe deterministic text normalizer
│   └── service.py    # Extraction orchestration service
├── schemas/          # Pydantic models for invoices & evidence
├── validation/       # Schema & arithmetic business rule validators (Phase 4)
├── matching/         # Reference-record reconciliation (Future)
├── review/           # State management & human review audits (Phase 5)
└── reporting/        # CSV and JSON export generators (Phase 6)
```

For comprehensive architectural details, consult [`docs/architecture.md`](docs/architecture.md) and [`docs/decisions/0003-extraction-pipeline.md`](docs/decisions/0003-extraction-pipeline.md).

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

### 5.2 OCR Configuration (Optional for Scanned Documents)
To enable live OCR recognition on scanned/image-based PDFs:
1. Install [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki).
2. Add the installation folder to your system `PATH`, or set `DOCUMIND_TESSERACT_CMD` in `.env`:
   ```bash
   DOCUMIND_TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```
*Note: If Tesseract is not installed, digital PDF extraction remains 100% operational; scanned PDFs will report clear environmental warnings rather than failing.*

### 5.3 Running Extraction & Evaluation
```bash
# Run extraction evaluation across all 50 synthetic documents
python scripts/evaluate_extraction.py
```
Evaluation metrics are saved to [`reports/phase_3_extraction_evaluation.md`](reports/phase_3_extraction_evaluation.md).

### 5.4 Launch Streamlit Application
```bash
streamlit run app/Home.py
```
Open your browser at `http://localhost:8501` to test file ingestion and live hybrid extraction.

---

## 6. Running Tests & Quality Checks

Run the automated test suite (67 tests spanning unit and integration tiers):
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
| **Phase 3** | **Hybrid PDF Text Extraction & OCR Pipeline** | **Completed** |
| Phase 4 | Schema & Business Rules Validation | Scheduled |
| Phase 5 | Human Review Workflow & Evidence UI | Scheduled |
| Phase 6 | Structured Export & Comprehensive Evaluation | Scheduled |

---

## 8. License

This project is licensed under the MIT License - see the LICENSE file for details.
