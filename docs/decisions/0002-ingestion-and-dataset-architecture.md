# ADR 0002: Secure Ingestion and Synthetic Dataset Architecture

## Status
Accepted

## Context
Phase 2 requires a reproducible corpus of 50 synthetic invoices (30 digital with real vector text, 20 scanned with image-only pages) and a secure document ingestion subsystem. The ingestion subsystem must treat all uploaded files as untrusted inputs, enforce strict validation, isolate files in non-public storage, and provide metadata tracking independently of Streamlit or database engines.

## Decisions

1. **Deterministic Programmatic Dataset Generation**:
   Use `pymupdf` and `Pillow` to deterministically render 30 digital vector PDFs and 20 scanned image-only PDFs with a fixed random seed (default: 42).
   Use `deflate=True, clean=True, no_new_id=True` during PDF saving to guarantee bit-for-bit reproducible document binaries across environments.

2. **Gold-Standard Annotation Format**:
   Every generated document is accompanied by an individual JSON annotation aligned with DocuMind's core invoice schema. Annotations record explicit ground truth values, document characteristics (layout, DPI, skew, compression), and a dedicated registry of deliberately introduced challenges (missing fields, arithmetic mismatches, ambiguous dates, confusable characters, duplicate invoice numbers, scan degradations).

3. **Multi-Gated File Validation**:
   Enforce multi-stage validation prior to accepting any file:
   - Extension verification (`.pdf` case-insensitive).
   - Non-empty check (`size > 0`).
   - Maximum upload limit (`DOCUMIND_MAX_UPLOAD_SIZE_MB`, default 25MB).
   - Magic bytes / file signature inspection (`%PDF-` in header).
   - Parser compatibility and structural integrity check via `pymupdf.open()`.
   - Encrypted PDF rejection policy (`DOCUMIND_ALLOW_ENCRYPTED_PDFS=false`).
   - Maximum page count restriction (`DOCUMIND_MAX_PAGE_COUNT`, default 50).

4. **Atomic & Isolated Local Storage**:
   Uploaded documents are stored in UUIDv4-isolated folders under `DOCUMIND_STORAGE_DIR`. Filenames are sanitized, directory traversal sequences are blocked, and files are written to `.tmp` files and atomically renamed. Ingestion metadata is persisted alongside stored documents as `metadata.json`.

5. **Decoupled Ingestion Service**:
   `IngestionService` coordinates validation and storage independently of any web framework, enabling reuse in Streamlit, CLI tools, REST APIs, or background workers.

## Consequences
- **Positive**: Complete auditability; zero customer PII risk; deterministic test benchmarks; defense-in-depth against malicious uploads; modular architecture ready for Phase 3 extraction.
- **Negative**: Scanned PDFs require an external OCR binary (Tesseract) to extract text in Phase 3; encrypted documents cannot be processed unless decrypted beforehand.
