# DocuMind Evaluation Framework & Metrics

To objectively benchmark extraction accuracy, validation reliability, and operational efficiency, DocuMind defines a multi-dimensional evaluation methodology.

---

## 1. Field-Level Extraction Metrics

Each extracted field $f \in \{\text{invoice\_number}, \text{invoice\_date}, \text{vendor\_name}, \text{currency}, \text{subtotal}, \text{tax}, \text{total}\}$ is evaluated against ground truth annotations.

### 1.1 Precision, Recall, and F1-Score
For discrete fields (e.g. `invoice_number`, `currency`):
- **True Positive ($TP$)**: Field extracted and matches ground truth exactly or within allowable normalization rules.
- **False Positive ($FP$)**: Field extracted with an incorrect value, or extracted when not present in ground truth.
- **False Negative ($FN$)**: Field present in ground truth but missed by extraction.

$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}, \quad F_1 = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

### 1.2 Normalized Edit Distance & Fuzzy Matching
For text fields with acceptable minor OCR variances (e.g. `vendor_name`):
$$\text{Similarity}(s_1, s_2) = 1 - \frac{\text{Levenshtein}(s_1, s_2)}{\max(\text{len}(s_1), \text{len}(s_2))}$$
A threshold of $\ge 0.90$ is standard for fuzzy true positive classification.

### 1.3 Numeric & Date Tolerance
- **Monetary amounts** (`total`, `subtotal`, `tax`): Must match ground truth to within $\pm 0.01$ currency units.
- **Dates** (`invoice_date`): Evaluated after ISO-8601 parsing (`YYYY-MM-DD`). Formats must resolve to the identical calendar date.

---

## 2. Document-Level Accuracy Metrics

### 2.1 Complete Document Accuracy (Exact Match Ratio)
A document is categorized as **Completely Accurate** if and only if **all required fields** match ground truth:
$$\text{DocAccuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{all required fields accurate in doc } i)}{N}$$

### 2.2 Critical Field Accuracy
Weighting accuracy based on commercial criticality (e.g. `invoice_number`, `total`, `invoice_date` weighted higher than optional `tax` breakdowns).

---

## 3. Validation Metrics

Evaluating the ability of the validation layer to detect errors:
- **False Acceptance Rate (FAR)**: Percentage of incorrect extractions that passed validation checks without being flagged.
- **False Rejection Rate (FRR)**: Percentage of correct extractions that were erroneously flagged as invalid.
- **Arithmetic Consistency Capture Rate**: Percentage of arithmetic mismatches correctly caught by the $\text{subtotal} + \text{tax} = \text{total}$ rule.

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

## 5. Human Correction Rate (HCR)

In a human-in-the-loop workflow, minimizing manual intervention is critical:
$$\text{HCR} = \frac{\text{Total Fields Corrected by Human Reviewer}}{\text{Total Fields Extracted}} \times 100\%$$

- **Target Benchmark**: $\text{HCR} < 5\%$ on high-quality digital PDFs, and $< 15\%$ on noisy scanned documents.
- **Audit Tracking**: Every reviewer keystroke and field override will be logged in Phase 5 to continuously track HCR across document templates.
