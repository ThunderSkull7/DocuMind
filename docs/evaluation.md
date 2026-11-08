# DocuMind Evaluation Framework & Metrics

To objectively benchmark extraction accuracy, validation reliability, and operational efficiency, DocuMind defines a multi-dimensional evaluation methodology paired with a reproducible 50-document synthetic invoice corpus.

---

## 1. Synthetic Corpus Composition & Benchmarking Corpus

The Phase 2 synthetic corpus provides a gold-standard ground truth baseline for evaluation:

| Category | Count | Format | Primary Evaluation Purpose |
| :--- | :---: | :--- | :--- |
| **Digital Vector Invoices** | 30 | PDF with native text | Benchmarking native PyMuPDF coordinate & text parsing, regex/heuristic field extractors, and schema compliance. |
| **Scanned Raster Invoices** | 20 | PDF with embedded images (no native text) | Benchmarking Tesseract OCR fallback, image preprocessing, deskewing resilience, and character error rates. |
| **Total Corpus** | **50** | Validated PDF documents | Complete end-to-end extraction and two-tier validation evaluation. |

### 1.1 Intentional Edge Case Distribution

The corpus deliberately embeds edge cases to evaluate system robustness:

1. **Missing Fields**:
   - `DOC-SYN-007` & `DOC-SYN-035`: Missing invoice number.
   - `DOC-SYN-012` & `DOC-SYN-038`: Missing/exempt tax amount.
   - `DOC-SYN-018`: Missing vendor corporate name.
2. **Arithmetic Mismatches**:
   - `DOC-SYN-015` & `DOC-SYN-041`: Deliberate discrepancy ($\text{subtotal} + \text{tax} \ne \text{total}$) to test business rule validation.
3. **Ambiguous & Inconsistent Dates**:
   - `DOC-SYN-023`: Ambiguous date format (`03/04/2024` - March 4 vs. April 3).
   - `DOC-SYN-025`: Inconsistent timeline (invoice issuance date after stated payment due date).
4. **Number & Formatting Variations**:
   - `DOC-SYN-027`: European monetary format (dot thousand separator, comma decimal: `1.240,50 €`).
   - `DOC-SYN-029`: Visually confusable alphanumeric glyphs (`INV-0O1I1lB8`).
5. **Cross-Document Conflicts**:
   - `DOC-SYN-030` & `DOC-SYN-045`: Shared duplicate invoice number identifier (`INV-2024-DUP999`) across two distinct vendors.
6. **Optical Degradations**:
   - `DOC-SYN-031` to `DOC-SYN-050`: Controlled variations in resolution (150–300 DPI), rotation/skew (-2.5° to +1.8°), contrast factors, and JPEG compression artifacts.

---

## 2. Field-Level Extraction Metrics

Each extracted field $f \in \{\text{invoice\_number}, \text{invoice\_date}, \text{vendor\_name}, \text{currency}, \text{subtotal}, \text{tax}, \text{total}\}$ is evaluated against gold annotations.

### 2.1 Precision, Recall, and F1-Score
For discrete fields (e.g. `invoice_number`, `currency`):
- **True Positive ($TP$)**: Field extracted and matches ground truth exactly or within allowable normalization rules.
- **False Positive ($FP$)**: Field extracted with an incorrect value, or extracted when not present in ground truth.
- **False Negative ($FN$)**: Field present in ground truth but missed by extraction.

$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}, \quad F_1 = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

### 2.2 Normalized Edit Distance & Fuzzy Matching
For text fields with acceptable minor OCR variances (e.g. `vendor_name`):
$$\text{Similarity}(s_1, s_2) = 1 - \frac{\text{Levenshtein}(s_1, s_2)}{\max(\text{len}(s_1), \text{len}(s_2))}$$
A threshold of $\ge 0.90$ is standard for fuzzy true positive classification.

### 2.3 Numeric & Date Tolerance
- **Monetary amounts** (`total`, `subtotal`, `tax`): Must match ground truth to within $\pm 0.01$ currency units.
- **Dates** (`invoice_date`): Evaluated after ISO-8601 parsing (`YYYY-MM-DD`). Formats must resolve to the identical calendar date.

---

## 3. Document-Level Accuracy Metrics

### 3.1 Complete Document Accuracy (Exact Match Ratio)
A document is categorized as **Completely Accurate** if and only if **all required fields** match ground truth:
$$\text{DocAccuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{all required fields accurate in doc } i)}{N}$$

### 3.2 Critical Field Accuracy
Weighting accuracy based on commercial criticality (`invoice_number`, `total`, `invoice_date` weighted higher than optional `tax` breakdowns).

---

## 4. OCR Evaluation Considerations

When evaluating degraded or scanned documents routed through Tesseract:
- **Character Error Rate (CER)**:
  $$\text{CER} = \frac{S + D + I}{N_{\text{chars}}}$$
  where $S$ = substitutions, $D$ = deletions, $I$ = insertions.
- **Word Error Rate (WER)**:
  $$\text{WER} = \frac{S_w + D_w + I_w}{N_{\text{words}}}$$
- **Routing Accuracy**: Ratio of scanned vs. digital documents correctly routed to native parsing vs. OCR fallback.

---

## 5. Dataset Limitations & Future Evaluation Scope

- **Template Diversity**: While 5 distinct layout styles and multipage scenarios are included, commercial invoices display thousands of distinct layouts, watermarks, stamps, and handwritten annotations.
- **Language Scope**: The current corpus is primarily Latin-script/English with European currency representations. Multi-lingual corpora (e.g. Arabic, CJK, Cyrillic) are reserved for future international extensions.
- **Table Line Item Extraction**: Line-item table parsing will be benchmarked in Phase 4/5; current gold annotations focus on core invoice summary fields.
