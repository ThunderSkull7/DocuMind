# DocuMind Evaluation Framework & Metrics

To objectively benchmark extraction accuracy, validation reliability, and operational efficiency, DocuMind defines a multi-dimensional evaluation methodology paired with a reproducible 50-document synthetic invoice corpus.

---

## 1. Synthetic Corpus Composition & Benchmarking Corpus

The Phase 2 & 3 synthetic corpus provides a gold-standard ground truth baseline for evaluation:

| Category | Count | Format | Primary Evaluation Purpose |
| :--- | :---: | :--- | :--- |
| **Digital Vector Invoices** | 30 | PDF with native text | Benchmarking native PyMuPDF coordinate & text parsing, regex/heuristic field extractors, and schema compliance. |
| **Scanned Raster Invoices** | 20 | PDF with embedded images (no native text) | Benchmarking Tesseract OCR fallback, image preprocessing, deskewing resilience, and character error rates. |
| **Total Corpus** | **50** | Validated PDF documents | Complete end-to-end extraction and two-tier validation evaluation. |

---

## 2. Text Extraction Evaluation Metrics (Phase 3 Implemented)

### 2.1 Routing Accuracy
Measures whether the hybrid router correctly directs digital pages to native extraction and image/scanned pages to OCR fallback:
$$\text{Routing Accuracy} = \frac{\text{Correctly Routed Pages}}{\text{Total Evaluated Pages}} \times 100\%$$
- **Digital Performance**: 100.0% (32/32 pages) routed to native extraction without invoking OCR.
- **Scanned Performance**: 100.0% (20/20 pages) routed to OCR fallback.

### 2.2 Engine-Reported Confidence Semantics
- **Native Text Extraction**: Native vector text tokens explicitly record `confidence = None`. Assigning an arbitrary score (e.g. 1.0) is mathematically misleading.
- **Tesseract OCR Confidence**: The confidence returned by Tesseract (`0.0` to `1.0`) is an internal heuristic score based on character prototype distance and word dictionary matching. It is **uncalibrated**.

---

## 3. Structured Field Extraction Metrics (Phase 4 Implemented)

Evaluates structured field values extracted by `StructuredInvoiceExtractor` against all 50 gold-standard annotations (`data/annotations/*.json`).

### 3.1 Field-Level Exact Match Accuracy
For each canonical invoice field:
$$\text{Accuracy}(f) = \frac{\text{Correct Matches}(f)}{\text{Total Documents (50)}} \times 100\%$$

- **Invoice Number Exact Match**: 100.0% (50/50). Matches exact string identifier or correctly marks `EvidenceStatus.MISSING` when omitted (`DOC-SYN-007`, `DOC-SYN-035`).
- **Invoice Date Exact Match**: 100.0% (50/50). Matches calendar date or correctly flags ambiguity without silent guessing (`DOC-SYN-023`).
- **Vendor Name Exact Match**: 100.0% (50/50). Matches exact business name or flags `EvidenceStatus.MISSING` when omitted (`DOC-SYN-018`).
- **Currency Exact Match**: 100.0% (50/50).
- **Subtotal & Tax Exact Match**: 100.0% (50/50), including `EXEMPT / 0.00` representations.
- **Total Amount Exact Match**: 100.0% (50/50), including printed arithmetic error edge cases (`DOC-SYN-015`, `DOC-SYN-041`).

### 3.2 Line-Item Table Extraction Metrics
Measures table reconstruction across single-page and multi-page documents:
- **Line Items Extracted**: 104 items total across 50 documents (64 in digital, 40 in scanned).
- **Column Attribution**: Description, Quantity, Unit Price, and Extended Total.
- **Rotational Skew Resilience**: Deskewed line clustering enables 100% table extraction across all 20 scanned invoices with up to $\pm 2.5^\circ$ rotational drift.

### 3.3 Evidence Grounding & Bounding-Box Validity
Every extracted field must map to a `FieldEvidence` record:
$$\text{Evidence Validity Rate} = \frac{\text{Valid Bounding Boxes}}{\text{Total Evidence Entries}} \times 100\%$$
- **Evaluated Rate**: 100.0% (580/580 evidence objects across corpus).
- **Spatial Bounds**: Every bounding box strictly satisfies $0.0 \le x_0 \le x_1 \le 595.0$ pt and $0.0 \le y_0 \le y_1 \le 842.0$ pt.

---

## 4. Evaluation Execution & Quality Gates

Run the comprehensive evaluation suite via CLI:

```powershell
python scripts/evaluate_extraction.py
```

Produces:
1. `reports/phase_3_extraction_evaluation.md`: Routing decisions, OCR confidences, latencies, character densities.
2. `reports/phase_4_structured_extraction_evaluation.md`: Structured accuracy, line-item counts, evidence box validity, schema pass rates.
