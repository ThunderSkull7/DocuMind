# DocuMind Privacy & Security Architecture

DocuMind processes financial invoices, which regularly contain confidential corporate information, pricing structures, and Personally Identifiable Information (PII) such as personal addresses, bank details, and contact numbers. This document details the privacy and security principles enforced across the system.

---

## 1. Synthetic-Data-First Policy

To eliminate legal, regulatory (GDPR, CCPA, HIPAA), and data breach risks during development, testing, and continuous integration:

- **Strict Ban on Real Documents in Source Control**: No real customer or production invoices may be committed to git or stored in public test suites.
- **Programmatic Generation**: All test corpora, benchmark fixtures, and demonstration files are generated synthetically via programmatic templates (using `PyMuPDF`, `Pillow`, and synthetic business entity profiles).
- **Safe Directory Quarantine**: The `data/storage/` and `data/uploads/` runtime directories are explicitly excluded in `.gitignore`.

---

## 2. File Upload & Ingestion Security

File uploads represent a critical attack surface (e.g. zip/PDF bombs, embedded scripts, path traversal exploits, executable masquerading). Ingestion applies multi-layered defenses:

```mermaid
flowchart LR
    Upload["User Upload"] --> SizeCheck["Size Limit Check<br/>(<= 25MB)"]
    SizeCheck --> MIMECheck["Extension Check<br/>(.pdf)"]
    MIMECheck --> MagicCheck["Magic Bytes Verification<br/>(%PDF- in header)"]
    MagicCheck --> ParserCheck["Structural Integrity Check<br/>(PyMuPDF parsing)"]
    ParserCheck --> EncryptCheck["Encryption Check<br/>(Policy enforcement)"]
    EncryptCheck --> PageCheck["Page Ceiling Check<br/>(<= 50 pages)"]
    PageCheck --> Sanitization["Filename Sanitization<br/>(Path Traversal Prevention)"]
    Sanitization --> IsolatedStore["UUID-Isolated Atomic Storage"]
```

### 2.1 File Validation Controls
1. **Extension Enforcement**: Only `.pdf` files are permitted.
2. **Binary Signature Verification**: The binary stream is checked for the `%PDF-` header signature within the first 1024 bytes.
3. **Strict File Size Bounds**: Enforced 25MB default ceiling (`DOCUMIND_MAX_UPLOAD_SIZE_MB`) prevents memory exhaustion.
4. **Page Count Ceilings**: Documents exceeding `DOCUMIND_MAX_PAGE_COUNT` (default: 50 pages) are rejected to prevent computational denial-of-service during OCR and raster rendering.
5. **Encryption Policy**: Encrypted or password-protected PDFs are rejected by default (`DOCUMIND_ALLOW_ENCRYPTED_PDFS=false`).

### 2.2 Storage Controls & Path Traversal Prevention
1. **Filename Sanitization**: Client-supplied filenames are sanitized: basenames isolated, relative traversal (`..`) stripped, and special characters replaced with safe underscores.
2. **Isolated Storage Hierarchy**: Dedicated UUIDv4 folder per document (`data/storage/{document_id}/{sanitized_filename}.pdf`).
3. **Atomic Writes**: Content is written to a `.tmp` file, synced to disk (`os.fsync`), and atomically replaced.

---

## 3. Local OCR Privacy & Resource Protection (Phase 3)

### 3.1 Local-First Execution
- The hybrid extraction engine operates **entirely offline** within the host environment.
- Native text parsing (PyMuPDF) and OCR fallback (local Tesseract binary) process document bytes in local memory without communicating over third-party networks or remote cloud APIs.

### 3.2 In-Memory Page Rendering & Ephemeral Image Cleanup
- During OCR fallback, PDF pages are rasterized into uncompressed in-memory pixmaps (`pymupdf.Pixmap`) and wrapped as in-memory Pillow images (`io.BytesIO`).
- Rendered page raster images are **never written to disk** or cached in temporary filesystem directories, preventing forensic recovery of unencrypted invoice page bitmaps.
- PyMuPDF documents and Pillow image handles are explicitly closed within `finally` blocks to free OS file descriptors and heap allocations.

### 3.3 OCR Timeout & Denial-of-Service Defense
- OCR operations enforce a strict execution timeout (`DOCUMIND_OCR_TIMEOUT_SECONDS`, default: 30 seconds). Runaway OCR processes on dense or corrupted raster images are terminated with `OCRTimeoutError`.
- Configurable rendering DPI (`DOCUMIND_OCR_DPI`, default: 300) prevents excessive memory consumption associated with ultra-high resolution image rasterization.

---

## 4. Sensitive Information & Logging Restrictions

- **Zero-PII Logging Principle**: Log messages must never output full raw text streams, bank account numbers, tax identification numbers, or user credit card details.
- **Metadata-Only Logging**: Logging statements record document identifiers, processing timings, status transitions, and error codes:
  * ✅ *Good*: `Stored document id=f47ac10b... size=142KB pages=2 duration=12.4ms`
  * ❌ *Prohibited*: `Parsed text: "Vendor John Doe Bank IBAN US123456789 Total $1,200"`
- **Sanitized Exception Handling**: Uncaught exceptions bubble up clean diagnostic messages rather than raw document buffers.

---

## 5. Residual Security Risks & Sandboxing Guidance

1. **Underlying C-Parser Vulnerabilities**: PyMuPDF and Tesseract execute native C/C++ code. Complex or maliciously crafted PDF constructs could theoretically trigger memory faults.
   * *Mitigation for Untrusted Public Deployments*: Run the ingestion and extraction service in an unprivileged, isolated container sandbox (e.g. gVisor, Docker container with seccomp/AppArmor profiles, or read-only ephemeral microVM).
2. **Decompression Bombs (Zip/PDF FlateBombs)**: Heavily compressed streams that expand to gigabytes upon decompression.
   * *Mitigation*: PyMuPDF sets internal stream expansion ceilings; maximum upload size limits (25MB) mitigate large input payloads.
