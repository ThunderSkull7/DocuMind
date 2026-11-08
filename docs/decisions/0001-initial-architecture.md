# ADR 0001: Initial Architecture and Foundation Selection

## Status
Accepted

## Context
DocuMind requires an extensible, robust, and maintainable foundation for automated invoice extraction, schema and business validation, human-in-the-loop verification, and reporting. The solution must process both digital native PDFs and scanned document images while remaining privacy-safe, lightweight, and easy to run locally or in containerized environments.

## Decisions

1. **Monolithic Modular Layout**:
   Organize the codebase under `src/documind/` with dedicated subpackages for `ingestion`, `extraction`, `schemas`, `validation`, `matching`, `review`, and `reporting`. Avoid premature microservice overhead.

2. **PyMuPDF (fitz) for Native PDF Parsing**:
   Use `pymupdf` as the primary engine for digital PDFs. It provides superior parsing performance, native word and character coordinates for bounding boxes, and fast page rendering.

3. **Tesseract OCR as Privacy-Preserving Fallback**:
   Use `pytesseract` to wrap local Tesseract OCR. This ensures scanned or low-text PDFs can be processed without transmitting sensitive financial documents to external third-party cloud APIs.

4. **Pydantic v2 for Structured Data & Validation**:
   Use Pydantic models for data typing, schema validation, and serialization. Pydantic provides type-safe models, fast Rust-based validation core, and seamless JSON schema generation.

5. **Streamlit for User Interface**:
   Use Streamlit for the primary interaction surface. It enables fast, reactive UI development with native support for file uploads, table previews, and review dashboards without requiring a decoupled React/Node stack.

6. **Centralized Configuration with Pydantic-Settings**:
   Use `pydantic-settings` to manage environment variables (`DOCUMIND_*`) with fallback defaults and dynamic relative path resolution. Absolute paths and machine-specific configs are prohibited.

7. **Pytest for Automated Verification**:
   Use `pytest` across unit, integration, and evaluation tiers with strict markers and pythonpath configuration.

## Consequences
- **Positive**: Clean separation of concerns; fast local development loop; completely offline capability; strong type guarantees.
- **Negative**: Requires local Tesseract binary installation for full OCR functionality; single-node processing limits initial scaling until asynchronous job workers are introduced in later stages if needed.
