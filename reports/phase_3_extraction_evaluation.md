# DocuMind Phase 3 — Hybrid PDF Text Extraction & OCR Evaluation Report

**Evaluation Date**: 2026-11-08
**DocuMind Version**: 0.1.0
**Engine Environment**: PyMuPDF `2.1`, Tesseract OCR binary: `C:\Program Files\Tesseract-OCR\tesseract.exe` (Available: `True`)

---

## 1. Executive Summary & Verification Verdict

This report establishes the empirical performance and verification of DocuMind's hybrid extraction pipeline across the complete 50-document synthetic invoice corpus (30 digital vector PDFs, 20 scanned image-based PDFs).

### Benchmark Matrix

| Metric | Digital Corpus (30 docs) | Scanned Corpus (20 docs) | Total Corpus (50 docs) |
| :--- | :---: | :---: | :---: |
| **Documents Evaluated** | 30 | 20 | 50 |
| **Total Pages Processed** | 32 | 20 | 52 |
| **Native Text Routing Rate** | **100.0%** (32/32) | 0.0% (0/20) | 61.5% (32/52) |
| **OCR Fallback Routing Rate** | 0.0% (0/32) | **100.0%** (20/20) | 38.5% (20/52) |
| **Extraction Success Rate** | **100.0%** (30/30) | **100.0%** (20/20) | **100.0%** (50/50) |
| **Total Errors / Timeouts** | 0 | 0 | 0 |
| **Avg. Characters / Page** | 512.3 chars | 516.1 chars | 513.8 chars |
| **Avg. Words / Page** | 77.5 words | 78.5 words | 77.9 words |
| **Avg. Word Bounding Boxes** | 77.5 / page | 78.5 / page | — |
| **Mean OCR Confidence** | `None` (Explicit) | **0.9405** (Uncalibrated) | — |
| **Avg. Latency / Document** | 2.49 ms | 1001.70 ms | 422.49 ms |

---

## 2. Extraction Configuration & Thresholds

- `DOCUMIND_ROUTING_MIN_CHAR_COUNT`: `50` characters
- `DOCUMIND_ROUTING_MIN_ALPHA_RATIO`: `0.4` (40% alphanumeric ratio)
- `DOCUMIND_ROUTING_MIN_WORD_COUNT`: `5` words
- `DOCUMIND_OCR_ENABLED`: `True`
- `DOCUMIND_OCR_DPI`: `300` DPI
- `DOCUMIND_OCR_PSM`: `3` (Fully automatic page segmentation)
- `DOCUMIND_OCR_TIMEOUT_SECONDS`: `30` seconds

---

## 3. Real OCR Verification on Scanned Documents (20 Invoices)

All 20 scanned, image-only invoices (`DOC-SYN-031` to `DOC-SYN-050`) were processed using local Tesseract 5.4.0:

### 3.1 Verification Checklist
- **OCR Invocation**: 100% (20/20) of scanned documents were correctly detected as lacking native text and routed to the OCR fallback engine.
- **Non-Empty Text**: 100% (20/20) produced non-empty text (range: 461 to 538 characters; mean: 516.1 chars).
- **Spatial Tokens & Bounding Boxes**: Every word recognized by Tesseract was transformed from pixel space to PDF point space (`x0, y0, x1, y1`) and verified to fit within the page dimensions (595.0 pt x 842.0 pt).
- **Confidence Values**: All OCR spatial tokens populated engine confidence scores (mean page confidence: 0.9405, min: 0.9292, max: 0.9489).
- **Zero Errors / Zero Timeouts**: No page failed or timed out during OCR execution.

### 3.2 Ground-Truth Field Presence in OCR Output
Evaluating raw substring occurrences of gold-standard values in the normalized OCR output:
- **Invoice Number Presence**: 20/20 (100.0%) matched or correctly absent when deliberately omitted (`DOC-SYN-035`).
- **Vendor Name Presence**: 20/20 (100.0%) matched.
- **Total Amount Presence**: 20/20 (100.0%) matched.

### 3.3 Uncalibrated Confidence Notice
As established in ADR 0003:
> The confidence scores reported by Tesseract (0.93–0.95) represent internal character prototype distance metrics and dictionary bonuses. They are **uncalibrated heuristic scores**, not statistical posterior probabilities.

---

## 4. Digital PDF Native Extraction (30 Invoices)

All 30 digital vector documents (`DOC-SYN-001` to `DOC-SYN-030`) were evaluated:
- **Routing Decision**: 100% routed to native extraction. Zero digital pages triggered unnecessary OCR fallback.
- **Extraction Fidelity**: Minimum 416 chars, maximum 543 chars.
- **Multipage Handling**: Multipage documents `DOC-SYN-010` and `DOC-SYN-028` preserved page boundaries with both pages extracted in reading order.
- **Confidence Provenance**: Native vector text explicitly recorded `confidence = None`.

---

## 5. Per-Document Scanned Extraction Breakdown

| Document ID | Layout Style | Skew Angle | DPI | OCR Words | OCR Chars | Avg. Conf | Duration | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `DOC-SYN-031` | scanned | variance | 300 | 79 | 517 | 0.93 | 969.6 ms | ✅ success |
| `DOC-SYN-032` | scanned | variance | 300 | 78 | 515 | 0.95 | 958.3 ms | ✅ success |
| `DOC-SYN-033` | scanned | variance | 300 | 80 | 538 | 0.94 | 997.7 ms | ✅ success |
| `DOC-SYN-034` | scanned | variance | 300 | 78 | 517 | 0.95 | 1010.9 ms | ✅ success |
| `DOC-SYN-035` | scanned | variance | 300 | 79 | 516 | 0.95 | 908.3 ms | ✅ success |
| `DOC-SYN-036` | scanned | variance | 300 | 81 | 507 | 0.94 | 1028.5 ms | ✅ success |
| `DOC-SYN-037` | scanned | variance | 300 | 79 | 516 | 0.93 | 968.8 ms | ✅ success |
| `DOC-SYN-038` | scanned | variance | 300 | 80 | 528 | 0.94 | 987.2 ms | ✅ success |
| `DOC-SYN-039` | scanned | variance | 300 | 76 | 514 | 0.95 | 1064.1 ms | ✅ success |
| `DOC-SYN-040` | scanned | variance | 300 | 80 | 527 | 0.95 | 1057.0 ms | ✅ success |
| `DOC-SYN-041` | scanned | variance | 300 | 76 | 497 | 0.93 | 1013.7 ms | ✅ success |
| `DOC-SYN-042` | scanned | variance | 300 | 70 | 461 | 0.93 | 991.0 ms | ✅ success |
| `DOC-SYN-043` | scanned | variance | 300 | 80 | 535 | 0.94 | 992.1 ms | ✅ success |
| `DOC-SYN-044` | scanned | variance | 300 | 80 | 532 | 0.95 | 1031.3 ms | ✅ success |
| `DOC-SYN-045` | scanned | variance | 300 | 77 | 527 | 0.94 | 1018.8 ms | ✅ success |
| `DOC-SYN-046` | scanned | variance | 300 | 79 | 502 | 0.94 | 1062.2 ms | ✅ success |
| `DOC-SYN-047` | scanned | variance | 300 | 79 | 513 | 0.94 | 953.5 ms | ✅ success |
| `DOC-SYN-048` | scanned | variance | 300 | 81 | 518 | 0.95 | 1009.9 ms | ✅ success |
| `DOC-SYN-049` | scanned | variance | 300 | 76 | 507 | 0.94 | 930.1 ms | ✅ success |
| `DOC-SYN-050` | scanned | variance | 300 | 81 | 536 | 0.94 | 1081.0 ms | ✅ success |

---

## 6. Known Limitations

1. **OCR Latency vs. Native Speed**: Native digital text extraction averages ~2.7 ms per document, while 300 DPI rasterization and Tesseract OCR averages ~700–1200 ms per document.
2. **Degraded & Skewed Text Variances**: In heavy skew scenarios (e.g. ±2.5°), word bounding boxes may span slight vertical drift, which structured field extraction in Phase 4 must account for using tolerance bands.
