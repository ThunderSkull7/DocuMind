# DocuMind Data Directory

This directory houses document assets, synthetic invoices, annotations, and local runtime storage for DocuMind.

## Directory Structure

```text
data/
├── README.md               # This documentation
├── synthetic_documents/    # Generated synthetic PDFs (Phase 2)
│   ├── digital/            # Native digital PDF invoices
│   └── scanned/            # Simulated scanned/degraded PDFs for OCR testing
├── annotations/            # Ground truth annotations in JSON/JSONL format
├── storage/                # Ingested uploaded documents (ignored by git)
└── cache/                  # Extraction and rendering cache (ignored by git)
```

## Security & Privacy Policy

- **Synthetic-Data-First**: Only synthetic, non-sensitive, generated documents and ground truth annotations are checked into version control.
- **No Real Customer Data**: Under no circumstances should real commercial invoices, Personally Identifiable Information (PII), or confidential corporate records be stored or committed here.
- **Git Ignored Storage**: The `storage/` and `cache/` runtime directories are explicitly ignored by `.gitignore` to prevent accidental commits of uploaded user documents.
