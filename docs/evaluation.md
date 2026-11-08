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

## 2. Text Extraction Evaluation Metrics (Phase 3)

### 2.1 Routing Accuracy
Measures whether the hybrid router correctly directs digital pages to native extraction and image/scanned pages to OCR fallback:
$$\text{Routing Accuracy} = \frac{\text{Correctly Routed Pages}}{\text{Total Evaluated Pages}} \times 100\%$$
- **Digital Target**: 100% of digital pages routed to native extraction without invoking OCR.
- **Scanned Target**: 100% of image-only pages routed to OCR fallback.

### 2.2 Character Error Rate (CER) and Word Error Rate (WER)
When comparing raw or OCR text against gold-standard transcription ground truth:
$$\text{CER} = \frac{S + D + I}{N_{\text{chars}}}, \quad \text{WER} = \frac{S_w + D_w + I_w}{N_{\text{words}}}$$
where $S$ = substitutions, $D$ = deletions, $I$ = insertions.
- **Transcript Ground Truth Requirement**: Full-text CER/WER calculation requires complete page-level verbatim source transcripts. As synthetic invoices expand, page-level transcripts are compiled programmatically from the generator layout data to prevent using OCR output itself as ground truth.

### 2.3 Limitations of Engine-Reported Confidence
- **Native Text Extraction**: Digital PDF extraction using PyMuPDF extracts font-encoded characters directly from vector content streams. It does not perform statistical image recognition, so native text tokens explicitly record `confidence = None`. Assigning an arbitrary or artificial confidence score (e.g. 1.0) is mathematically misleading.
- **Tesseract OCR Confidence**: The confidence returned by Tesseract (`0.0` to `1.0`) is an internal heuristic score based on character prototype distance and word dictionary matching. It is **not** a calibrated posterior probability. A reported confidence of 0.85 does not mean an 85% probability of correctness.

---

## 3. Field-Level Extraction Metrics (Scheduled for Phase 4)

Each extracted field $f \in \{\text{invoice\_number}, \text{invoice\_date}, \text{vendor\_name}, \text{currency}, \text{subtotal}, \text{tax}, \text{total}\}$ is evaluated against gold annotations.

### 3.1 Precision, Recall, and F1-Score
For discrete fields (e.g. `invoice_number`, `currency`):
$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}, \quad F_1 = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

### 3.2 Normalized Edit Distance & Fuzzy Matching
For text fields with acceptable minor OCR variances (e.g. `vendor_name`):
$$\text{Similarity}(s_1, s_2) = 1 - \frac{\text{Levenshtein}(s_1, s_2)}{\max(\text{len}(s_1), \text{len}(s_2))}$$
A threshold of $\ge 0.90$ is standard for fuzzy true positive classification.

---

## 4. Document-Level Accuracy Metrics

### 4.1 Complete Document Accuracy (Exact Match Ratio)
$$\text{DocAccuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{all required fields accurate in doc } i)}{N}$$

---

## 5. Phase 3 Empirical Extraction Benchmark Summary

Measured across all 50 synthetic corpus documents (`reports/phase_3_extraction_evaluation.md`):
- **Digital Corpus Throughput**: 30 documents (32 pages) processed in 85.4 ms (average 2.67 ms/doc).
- **Native Routing Accuracy**: 100.0% (32/32 pages).
- **Scanned Routing Accuracy**: 100.0% (20/20 pages routed to OCR).
- **Bounding Box Conformity**: 100% of spatial tokens strictly contained within page boundary dimensions.
