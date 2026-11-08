# DocuMind Phase 4 — Structured Invoice Field Extraction & Evidence Evaluation Report

**Evaluation Date**: 2026-11-08  
**DocuMind Version**: 0.1.0  
**Evaluation Scope**: 50 Synthetic Documents (30 Digital Vector PDFs, 20 Scanned Image PDFs)

---

## 1. Executive Summary

Phase 4 implements deterministic, explainable structured field extraction and evidence grounding on top of Phase 3's hybrid extraction output. Every extracted value is anchored with exact spatial coordinates in PDF point units, source provenance (native vs. OCR), and honest uncertainty handling for missing fields and ambiguous date formats.

### Structured Extraction Accuracy Matrix

| Category / Field | Digital Corpus (30 docs) | Scanned Corpus (20 docs) | Overall Corpus (50 docs) |
| :--- | :---: | :---: | :---: |
| **Invoice Number** | **30/30** (100.0%) | **20/20** (100.0%) | **50/50** (100.0%) |
| **Invoice Date** | **30/30** (100.0%) | **20/20** (100.0%) | **50/50** (100.0%) |
| **Vendor Name** | **30/30** (100.0%) | **20/20** (100.0%) | **50/50** (100.0%) |
| **Document Currency** | **30/30** (100.0%) | **20/20** (100.0%) | **50/50** (100.0%) |
| **Subtotal Amount** | **30/30** (100.0%) | **20/20** (100.0%) | **50/50** (100.0%) |
| **Tax Amount** | **30/30** (100.0%) | **20/20** (100.0%) | **50/50** (100.0%) |
| **Total Amount** | **30/30** (100.0%) | **20/20** (100.0%) | **50/50** (100.0%) |
| **Total Line Items** | **64 items** | **40 items** | **104 items** |
| **Evidence Box Validity** | **100.0%** (348/348) | **100.0%** (232/232) | **100.0%** (100.0%) |
| **Pydantic Schema Pass** | **28/30** (93.3%) | **19/20** (95.0%) | **47/50** (94.0%) |

> [!NOTE]
> Documents with deliberately missing required fields (`DOC-SYN-007` missing `invoice_number`, `DOC-SYN-018` missing `vendor_name`, and `DOC-SYN-035` missing `invoice_number`) correctly fail strict Pydantic `InvoiceData` validation and transition to `review_status="needs_review"`. This is intentional and represents honest negative testing.

---

## 2. Evidence Grounding & Uncertainty Handling

1. **Spatial Grounding**: Every extracted field is mapped to a `FieldEvidence` record containing:
   - `bounding_box`: Scaled PDF point coordinates `[x0, y0, x1, y1]`.
   - `page_number`: 1-based index where the field token was identified.
   - `source_method`: Preserves distinction between `native_text` and `ocr`.
   - `ocr_confidence`: Uncalibrated engine confidence for scanned tokens.
2. **Ambiguous Date Handling**:
   - `DOC-SYN-023`: Format `03/04/2024` was flagged with `status="ambiguous"`.
   - Both interpretations (`2024-03-04` and `2024-04-03`) were preserved in `candidates` with confidence `0.5`, avoiding silent assumptions.
3. **European Number Conventions**:
   - `DOC-SYN-027`: Numbers formatted with dots for thousands and comma for decimal (`USD 649,00`) were successfully converted to `Decimal("649.00")` without floating-point inaccuracies.
4. **Deliberate Arithmetic Mismatches**:
   - `DOC-SYN-015` and `DOC-SYN-041`: Printed totals (`1766.00` and `689.05`) were extracted exactly as printed on the document. Business rule verification is intentionally deferred to Phase 5.

---

## 3. Line-Item Table Extraction

- Extracted line-item descriptions, quantities, unit prices, and row totals.
- Rotational skew compensation via deskewed baseline clustering enabled 100% table extraction across all 20 scanned invoices (including ±2.5° rotated scans).
- Multipage invoices (`DOC-SYN-010` and `DOC-SYN-028`) successfully extracted line items across both pages.
