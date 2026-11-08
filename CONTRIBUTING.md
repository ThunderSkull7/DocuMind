# Contributing to DocuMind

Thank you for your interest in contributing to DocuMind! DocuMind is an intelligent document extraction, verification, and human review system engineered for financial documents.

---

## 1. Development Setup

### 1.1 Prerequisites
- **Python**: Version 3.10, 3.11, or 3.12 (Python 3.12 recommended).
- **Tesseract OCR (Optional for live scanned PDF testing)**: Version 5.x.

### 1.2 Local Setup (Windows PowerShell)
```powershell
# Clone the repository
git clone https://github.com/ThunderSkull7/DocuMind.git
cd DocuMind

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install editable package with dev dependencies
pip install -e ".[dev]"

# Copy configuration
cp .env.example .env
```

---

## 2. Coding Standards & Tooling

We enforce strict formatting and linting via [Ruff](https://github.com/astral-sh/ruff):

```powershell
# Run Ruff linting
ruff check .

# Check Ruff formatting
ruff format --check .

# Auto-format codebase
ruff format .
```

### Core Architecture Rules
1. **Preserve Immutability**: Extraction records and raw evidence bounding boxes must remain immutable once created. Reviewer edits must be captured non-destructively as distinct revision records.
2. **Fixed-Point Arithmetic**: Financial comparisons and calculations must use Python's `Decimal` with fixed-point rounding (`ROUND_HALF_UP`) to prevent floating-point drift.
3. **Local Privacy Boundary**: DocuMind executes 100% locally. Do not introduce dependencies that perform unvetted outbound network requests or external cloud telemetry.
4. **Formula Injection Sanitization (CWE-1236)**: Ensure all tabular export values are routed through `sanitize_csv_value()`.

---

## 3. Testing Requirements

All contributions must include unit or integration tests:

```powershell
# Run the complete test suite
pytest -v

# Run test suite with code coverage
pytest -v --cov=src/documind --cov-report=term-missing

# Run the 50-document evaluation benchmark
python scripts/evaluate_extraction.py
```

---

## 4. Document Data Guidelines

- **Synthetic Only**: Never commit real, confidential, or customer financial invoices.
- **Reproducible Dataset**: When adding test documents, use the synthetic generator in `src/documind/dataset/generator.py` or synthetic fixtures.

---

## 5. Pull Request Process

1. Create a feature branch: `git checkout -b feature/my-enhancement`.
2. Commit your changes with clear, semantic commit messages.
3. Verify all tests and Ruff checks pass locally.
4. Submit a Pull Request targeting the `main` branch using the provided PR template.

