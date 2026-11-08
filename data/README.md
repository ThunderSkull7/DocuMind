# DocuMind Data Directory

This directory houses document assets, synthetic invoices, gold-standard annotations, and local runtime storage for DocuMind.

---

## 1. Directory Structure

```text
data/
├── README.md               # This documentation
├── manifest.json           # Catalog of all 50 corpus documents, hashes, and characteristics
├── synthetic_documents/    # 50 reproducible synthetic invoice PDFs
│   ├── syn_invoice_001_digital.pdf ... syn_invoice_030_digital.pdf
│   └── syn_invoice_031_scanned.pdf ... syn_invoice_050_scanned.pdf
├── annotations/            # 50 gold-standard JSON annotations
│   ├── DOC-SYN-001.json ... DOC-SYN-050.json
├── storage/                # Safe ingested document storage (ignored by git)
└── cache/                  # Extraction and rendering cache (ignored by git)
```

---

## 2. Corpus Composition & Generation

The dataset comprises **50 synthetic invoice documents**:
- **30 Digital PDFs** (`syn_invoice_001_digital.pdf` to `syn_invoice_030_digital.pdf`): Vector text documents generated using multiple layout templates (Modern Tech, Corporate Classic, Telecom Utility, Professional Services, European VAT, Multipage). All contain extractable text layers.
- **20 Scanned PDFs** (`syn_invoice_031_scanned.pdf` to `syn_invoice_050_scanned.pdf`): Raster image documents embedded into PDF pages without underlying text layers (`page.get_text() == ""`). Features controlled variances in resolution (150–300 DPI), rotation/skew (-2.5° to +1.8°), contrast scaling, and JPEG compression artifacts.

### Regeneration Command
To regenerate the corpus deterministically:
```bash
python scripts/generate_synthetic_dataset.py --seed 42
```
Using the default seed `42`, the generator produces identical file hashes matching [`manifest.json`](manifest.json).

---

## 3. Annotation Schema

Each invoice has an individual gold-standard annotation file named `{document_id}.json`.

Example annotation (`data/annotations/DOC-SYN-015.json`):
```json
{
  "document_id": "DOC-SYN-015",
  "file_name": "syn_invoice_015_digital.pdf",
  "document_type": "digital",
  "invoice_number": "INV-2024-0015",
  "invoice_date": "2024-04-06",
  "vendor_name": "Apex Cloud Systems Inc.",
  "currency": "USD",
  "subtotal": "595.50",
  "tax": "59.55",
  "total": "705.05",
  "characteristics": {
    "layout_template": "european_vat",
    "page_count": 1,
    "is_scanned": false,
    "resolution_dpi": 300,
    "rotation_degrees": 0.0,
    "jpeg_quality": null,
    "contrast_factor": 1.0
  },
  "deliberately_introduced_issues": [
    {
      "issue_type": "arithmetic_mismatch",
      "field": "total",
      "description": "Total amount on document intentionally does not equal subtotal + tax",
      "expected_extracted": "705.05",
      "ground_truth_actual": "655.05"
    }
  ]
}
```

---

## 4. Synthetic-Data-First Privacy Policy

- **Strict Ban on Real Documents**: Under no circumstances should real commercial invoices, Personally Identifiable Information (PII), or confidential corporate records be stored or committed here.
- **Fictional Master Data**: All company names, addresses, tax IDs, and line items are fictional and generated programmatically.
- **Quarantine**: Ingested runtime documents in `storage/` and cache files in `cache/` are explicitly ignored by `.gitignore`.
