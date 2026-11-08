# ADR 0005: Deterministic Business Rule Validation, Arithmetic Consistency & Discrepancy Detection

## Status
Accepted

## Context
Following Phase 4's structured field extraction and evidence grounding, extracted invoice records must undergo rigorous business and financial validation. Invoice documents in real-world accounts payable workflows exhibit arithmetic errors (miscalculated totals, incorrect line item multiplications), missing required business metadata (omitted invoice numbers or vendor identities), suspicious values (zero or negative totals, non-ISO currency codes), ambiguous dates, duplicate submissions (identical documents, duplicate billing numbers, or cross-vendor identifier collisions), and mismatches against enterprise reference data (vendor master records and purchase orders).

The validation subsystem must be deterministic, explainable, reproducible, and strictly non-destructive—preserving the original extraction evidence without silent mutation or deletion.

## Decisions

1. **Fixed-Point `Decimal` Arithmetic Engine**:
   All financial validations (line-item quantity $\times$ unit price, sum of line items vs. subtotal, subtotal $+$ tax $+$ shipping $-$ discount vs. total, and balance due vs. total $-$ amount paid) are executed using Python's `Decimal` type with fixed scale. A configurable arithmetic tolerance (default: \$0.01) accounts for standard half-up rounding in sales tax calculations while preventing IEEE 754 floating-point drift.

2. **Structured Discrepancy Model with Direct Evidence Grounding**:
   Every validation failure or warning generates an immutable `Discrepancy` record:
   - Identifiers: `discrepancy_id`, `rule_id` (e.g. `ARITH_001`, `BIZ_001`, `DUP_001`, `REF_001`), `category` (`RuleCategory`), and `severity` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
   - Audit trail: `affected_fields`, `expected_value`, `actual_value`, `difference`, human-readable `explanation`, and `suggested_action`.
   - Evidence grounding: `evidence_ids` referencing original `FieldEvidence` keys, plus `evidence_snippets` embedding bounding box coordinates and source method (`native_text` vs. `ocr`).

3. **Deterministic Multi-Tier Duplicate Detection**:
   Duplicate detection operates across four distinct levels:
   - **Exact Hash Duplicate (`DUP_000`)**: Identical SHA-256 payload hash (document-level duplicate).
   - **Exact Identity Duplicate (`DUP_001`)**: Same vendor name and invoice number across different files.
   - **Cross-Vendor Identifier Collision (`DUP_003`)**: Shared invoice number across different vendors, common in invoice number collision scenarios.
   - **Potential Duplicate (`DUP_002`)**: Substantially similar invoice numbers ($\ge 0.85$ Levenshtein ratio), identical total amounts, and dates within a 14-day temporal window.

4. **Reference Data Matching (Vendor Master & Purchase Orders)**:
   A dedicated `ReferenceMatcher` validates extracted invoices against external ERP/accounting databases:
   - **Vendor Master Matching (`REF_001`)**: Exact or normalized string matching against active vendor registries, checking vendor status and flagged tax IDs.
   - **PO Number Reconciliation (`REF_002`)**: Verifies existence and open status of stated purchase orders.
   - **PO Total & Line Match (`REF_003`)**: Verifies invoice total does not exceed authorized PO amounts.

5. **Hierarchical Document Status Determination**:
   Validation results roll up into a single deterministic document status:
   - `INVALID`: Presence of any `CRITICAL` severity discrepancy (e.g., missing invoice number or vendor name).
   - `NEEDS_REVIEW`: Presence of any `HIGH` severity discrepancy (e.g., arithmetic total mismatch $> \$0.01$, exact duplicate billing).
   - `VALID_WITH_WARNINGS`: Presence of `MEDIUM` or `LOW` discrepancies (e.g., ambiguous date format, cross-vendor identifier collision, visually confusable characters).
   - `VALID`: Zero discrepancies or only `INFO` severity notices.
   - `INDETERMINATE`: Crucial data points missing such that validation cannot be reliably evaluated.

6. **Strict Non-Destructive Operation**:
   Validation is an audit and verification layer. It never alters `InvoiceExtractionRecord`, never overwrites extracted text, and never deletes or merges duplicate records automatically.

## Consequences
- **Positive**: Complete financial audit trail; 100% reproducible discrepancies; precise bounding box links in UI for human reviewer inspection; transparent separation of extraction from business logic.
- **Negative**: High-skew OCR text may trigger arithmetic mismatches if an OCR digit is misrecognized, requiring human review; however, this is the desired behavior for financial risk mitigation.
