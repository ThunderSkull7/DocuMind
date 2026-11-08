# DocuMind Phase 5 — Business Rule Validation & Discrepancy Detection Evaluation Report

**Evaluation Date**: 2026-11-08
**DocuMind Version**: 0.1.0
**Evaluation Scope**: 50 Synthetic Documents (30 Digital Vector PDFs, 20 Scanned Image PDFs)
**Execution Mode**: Deterministic Fixed-Point Decimal Validation & Multi-Tier Screening

---

## 1. Executive Summary & Verification Verdict

Phase 5 introduces a deterministic business validation subsystem that screens structured invoice records produced by Phase 4. It executes line-item and tax arithmetic consistency checks, mandatory field completeness checks, temporal consistency checks, multi-tier duplicate detection (exact payload hash, exact vendor-invoice identity, cross-vendor identifier collision, and temporal-amount similarity), and reference data matching against vendor master records and purchase orders.

The validation subsystem operates non-destructively: all findings are recorded as structured `Discrepancy` models grounded in original bounding-box evidence, and no document or extracted field is mutated.

### Document Validation Status Distribution

| Overall Status | Digital Invoices (30 docs) | Scanned Invoices (20 docs) | Total Corpus (50 docs) | Percentage |
| :--- | :---: | :---: | :---: | :---: |
| **`VALID`** | **25** (83.3%) | **17** (85.0%) | **42** (84.0%) | 84.0% |
| **`VALID_WITH_WARNINGS`** | **2** (6.7%) | **0** (0.0%) | **2** (4.0%) | 4.0% |
| **`NEEDS_REVIEW`** | **1** (3.3%) | **2** (10.0%) | **3** (6.0%) | 6.0% |
| **`INVALID`** | **2** (6.7%) | **1** (5.0%) | **3** (6.0%) | 6.0% |
| **`INDETERMINATE`** | **0** (0.0%) | **0** (0.0%) | **0** (0.0%) | 0.0% |
| **Total** | **30** (100.0%) | **20** (100.0%) | **50** (100.0%) | 100.0% |

- **Mean Validation Latency**: 0.15 ms per document (excluding raw OCR rasterization).
- **Floating-Point Drift**: **Zero**. All arithmetic computations utilize `Decimal` with half-up cent precision.

---

## 2. Business Rules & Discrepancies Breakdown

### Active Rule Catalogue Performance

| Rule ID | Rule Name | Category | Severity | Triggered Docs | Corpus Occurrences |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **`BIZ_001`** | Mandatory Fields Completeness | Completeness | `CRITICAL` | `DOC-SYN-007`, `DOC-SYN-018`, `DOC-SYN-035` | 3 |
| **`ARITH_003`**| Subtotal + Tax + Shipping - Discount == Total | Arithmetic | `HIGH` | `DOC-SYN-015`, `DOC-SYN-041` | 2 |
| **`DUP_003`** | Shared Identifier Across Different Vendors | Duplicate | `MEDIUM` | `DOC-SYN-045` | 1 |
| **`BIZ_004`** | Ambiguous Numeric Date Format | Integrity | `MEDIUM` | `DOC-SYN-023` | 1 |
| **`BIZ_008`** | Visually Confusable OCR Glyphs | Integrity | `INFO` | `DOC-SYN-029` | 1 |
| **`ARITH_001`**| Line Item Qty * Unit Price == Row Total | Arithmetic | `HIGH` | None (All line items correct) | 0 |
| **`ARITH_002`**| Sum of Line Items == Subtotal | Arithmetic | `HIGH` | None (All sums correct) | 0 |
| **`DUP_000`** | Exact File Hash Duplicate | Duplicate | `HIGH` | None in single-pass corpus | 0 |
| **`DUP_001`** | Exact Vendor & Invoice Number Duplicate | Duplicate | `HIGH` | None in single-pass corpus | 0 |
| **`REF_001`** | Vendor Master Directory Matching | Reference | `HIGH` | Tested via isolated unit tests | 0 |

---

## 3. Detailed Edge Case Analysis (Deliberate Injections)

All synthetic edge cases deliberately injected during Phase 2 were accurately identified and classified:

### 3.1 Incomplete Invoices (`OverallValidationStatus.INVALID`)
1. **`DOC-SYN-007` (Digital)**:
   - Injected Issue: Explicitly missing `invoice_number` (`[Invoice Number: NOT SPECIFIED]`).
   - Outcome: Flagged by `BIZ_001` (`CRITICAL`), `OverallValidationStatus.INVALID`.
   - Action: Document rejected; human review required to assign identifier.
2. **`DOC-SYN-018` (Digital)**:
   - Injected Issue: Completely omitted vendor header and profile.
   - Outcome: Flagged by `BIZ_001` (`CRITICAL`), `OverallValidationStatus.INVALID`.
   - Action: Document rejected; missing vendor prevents AP routing.
3. **`DOC-SYN-035` (Scanned)**:
   - Injected Issue: Scanned invoice with omitted invoice number header.
   - Outcome: Flagged by `BIZ_001` (`CRITICAL`), `OverallValidationStatus.INVALID`.
   - Action: Rejected; prevents duplicate payment risk.

### 3.2 Arithmetic Mismatches (`OverallValidationStatus.NEEDS_REVIEW`)
1. **`DOC-SYN-015` (Digital)**:
   - Injected Issue: Printed total is `$1766.00` while calculated total ($1560.00 subtotal + $156.00 tax) is `$1716.00`.
   - Outcome: Flagged by `ARITH_003` (`HIGH`), discrepancy difference = `+$50.00`.
   - Action: `NEEDS_REVIEW`; flagged for AP discrepancy resolution.
2. **`DOC-SYN-041` (Scanned)**:
   - Injected Issue: Printed total is `$689.05` while calculated total ($535.50 subtotal + $53.55 tax) is `$589.05`.
   - Outcome: Flagged by `ARITH_003` (`HIGH`), discrepancy difference = `+$100.00`.
   - Action: `NEEDS_REVIEW`; highlighted in review queue.

### 3.3 Duplicate & Collision Screening (`OverallValidationStatus.NEEDS_REVIEW`)
1. **`DOC-SYN-045` (Scanned)**:
   - Injected Issue: Shares invoice number `INV-2024-DUP999` with digital invoice `DOC-SYN-030` under a different vendor (`Apex Logistics` vs `Apex Innovations`).
   - Outcome: Flagged by `DUP_003` (`MEDIUM`).
   - Action: `NEEDS_REVIEW`; alerts accounts payable to confirm distinct corporate entity.

### 3.4 Ambiguity & Glyph Warnings (`OverallValidationStatus.VALID_WITH_WARNINGS`)
1. **`DOC-SYN-023` (Digital)**:
   - Injected Issue: Ambiguous slash date `03/04/2024` (March 4 vs April 3).
   - Outcome: Flagged by `BIZ_004` (`MEDIUM`). Evidence status set to `AMBIGUOUS` with both candidate dates preserved.
   - Action: `VALID_WITH_WARNINGS`; flagged for user confirmation of locale.
2. **`DOC-SYN-029` (Digital)**:
   - Injected Issue: Identifier `INV-0O1I1lB8` contains confusable `0`/`O` and `1`/`I`/`l`.
   - Outcome: Flagged by `BIZ_008` (`INFO`).
   - Action: `VALID_WITH_WARNINGS`; informational warning for data entry.

---

## 4. Verification of Core System Guarantees

1. **Non-Destructive Operations**:
   - `InvoiceExtractionRecord` instances and `FieldEvidence` tokens are never modified during validation.
   - Validation outputs are packaged into standalone `ValidationResult` objects containing immutable `Discrepancy` lists.
2. **Fixed-Point Precision**:
   - All arithmetic checks use Python `Decimal`. Floating-point drift (e.g. `0.1 + 0.2 != 0.3`) is completely prevented.
3. **Traceable Grounding**:
   - Every discrepancy links back to the specific fields involved (`affected_fields`), original bounding box coordinates (`evidence_snippets`), and a specific, actionable `review_recommendation`.
