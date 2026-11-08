# ADR 0004: Structured Invoice Field Extraction & Evidence Grounding

## Status
Accepted

## Context
Phase 4 requires transforming the raw page-level hybrid extraction output from Phase 3 into structured, machine-readable invoice records (`InvoiceData`) with end-to-end provenance (`FieldEvidence`). The system must extract invoice header fields, vendor/customer profiles, financial summaries, and line-item tables without relying on external cloud LLMs or paid APIs, while handling deliberate edge cases (missing fields, ambiguous dates, rotational skew, European numbers, and arithmetic mismatches).

## Decisions

1. **Deterministic Spatial and Keyword Hybrid Extraction**:
   Field identification combines keyword/label proximity matching with spatial reading-order analysis. Values appearing horizontally beside labels (same line, $x > x_{\text{label}}$) or directly below labels (within vertical bands) are extracted deterministically.

2. **Rotational Skew Compensation via Deskewed Line Clustering**:
   Scanned documents frequently exhibit minor rotational skew ($\pm 2.5^\circ$), causing text on a single printed line to drift vertically by 10–20 points across the page width. We compute the median slope across horizontally proximate words and project coordinates onto a deskewed baseline:
   $$y' = y - x \cdot \tan(\theta)$$
   This ensures words spanning the entire page width (e.g., in table header rows and line-item rows) cluster into coherent lines without row splitting.

3. **Traceable Grounding Evidence for Every Field**:
   Every field maps to a `FieldEvidence` record containing:
   - `bounding_box`: Scaled bounding box in PDF point units enclosing all constituent words.
   - `page_number`: 1-indexed document page where the token resides.
   - `source_method`: Preserves distinction between `native_text` and `ocr`.
   - `ocr_confidence`: Uncalibrated engine confidence for scanned tokens.
   - `status`: Explicit state (`extracted`, `missing`, `ambiguous`, `needs_review`).

4. **Honest Ambiguity and Missing Value Representation**:
   - When a field is explicitly omitted (e.g. `[Invoice Number: NOT SPECIFIED]` or omitted vendor headers), the extractor sets the value to `None` with `status=EvidenceStatus.MISSING` rather than hallucinating or accepting unreliable text.
   - When a numeric date is ambiguous (e.g. `03/04/2024` where both day and month $\le 12$), the extractor records `status=EvidenceStatus.AMBIGUOUS` and populates `candidates=["2024-03-04", "2024-04-03"]`.

5. **Fixed-Point Decimal Financial Precision**:
   All monetary amounts are parsed into Python `Decimal` instances across Anglo (`1,234.56`) and European (`1.234,56` or `649,00`) conventions without IEEE 754 floating-point drift.

6. **Strict Schema vs. Business Rule Boundary**:
   Phase 4 strictly validates Pydantic data types, mandatory field presence, date validity, and coordinate bounds. Business validation (arithmetic consistency `subtotal + tax == total`, duplicate detection, tax compliance) is intentionally deferred to Phase 5. Invoices with printed arithmetic errors (e.g. `DOC-SYN-015`) accurately extract the printed total.

## Consequences
- **Positive**: 100% deterministic, explainable extraction across both digital and scanned documents; zero external API or network dependencies; full spatial auditability; robust handling of scan skew.
- **Negative**: Extraction rules rely on standard invoice layout topologies; highly exotic or unlabelled artistic layouts may require fallback heuristics or human review.

