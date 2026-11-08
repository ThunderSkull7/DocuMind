# DocuMind Invoice Document Schema Specification

This document defines the formal schema, data types, validation constraints, and evidence metadata standards for invoices processed by DocuMind.

---

## 1. Core Invoice Fields

| Field Name | Type | Requirement | Format / Pattern | Description |
| :--- | :--- | :--- | :--- | :--- |
| `invoice_number` | `str` | **Required** | Length: 1–100 chars; Alphanumeric & symbols (`-`, `/`, `_`) | Unique identification number assigned by the vendor. |
| `invoice_date` | `date` | **Required** | ISO 8601 (`YYYY-MM-DD`) | Date on which the invoice was issued. |
| `vendor_name` | `str` | **Required** | Length: 1–200 chars | Legal corporate or trading name of the billing party. |
| `currency` | `str` | **Required** | ISO 4217 3-letter code (`USD`, `EUR`, `GBP`) or recognized symbol (`$`, `€`, `£`) | Currency in which monetary values are denoted. |
| `subtotal` | `Decimal` | *Optional* | Non-negative numeric (`>= 0.00`) with 2 decimal places | Net billable sum prior to applicable taxes and fees. |
| `tax` | `Decimal` | *Optional* | Non-negative numeric (`>= 0.00`) with 2 decimal places | Aggregated tax, VAT, or GST applied to the invoice. |
| `total` | `Decimal` | **Required** | Non-negative numeric (`>= 0.00`) with 2 decimal places | Final gross amount payable. |

---

## 2. Validation & Business Rules

### 2.1 Syntactic Validation
- **Non-empty Constraints**: Required string fields (`invoice_number`, `vendor_name`, `currency`) must not be empty or solely whitespace.
- **Date Parsability**: `invoice_date` must conform to standard date representations and resolve to a valid calendar date.
- **Monetary Precision**: All numeric monetary fields must be parsed into fixed-point `Decimal` instances to avoid IEEE 754 floating-point inaccuracies.

### 2.2 Semantic & Arithmetic Business Rules
1. **Total Consistency Rule**:
   $$\text{subtotal} + \text{tax} = \text{total}$$
   - When both `subtotal` and `tax` are present, their sum must match `total` within a tolerance of $\pm 0.02$ currency units (to accommodate standard rounding differences).
2. **Subtotal vs Total**:
   $$\text{subtotal} \le \text{total}$$
   - Unless an explicit credit or negative adjustment is registered, the subtotal cannot exceed the total.
3. **Temporal Validity**:
   - `invoice_date` must not be in the future (beyond a configurable grace threshold, e.g. 1 day for international timezone differences).
   - Invoices dated older than 10 years should trigger a warning flag for potential archival or stale entry.
4. **Currency Standardization**:
   - Currency symbols (`$`, `€`, `£`, `¥`) must be mapped to their canonical ISO 4217 code during normalization (e.g. `$` ➔ `USD` or specified regional default).

---

## 3. Evidence Grounding & Metadata

To guarantee auditability, every extracted value must be linked to an evidence record containing:

```json
{
  "raw_text": "INV-2024-00941",
  "confidence": 0.98,
  "method": "native_text",
  "page_number": 1,
  "bounding_box": {
    "page": 1,
    "x0": 420.5,
    "y0": 65.2,
    "x1": 530.8,
    "y1": 78.4
  }
}
```

### Evidence Attributes
- `raw_text`: The exact, unaltered string segment extracted from the PDF or OCR stream prior to normalization.
- `confidence`: Confidence score in the range `[0.0, 1.0]`. Native PDF extractions default to high confidence (`0.95–1.0`), whereas OCR extractions inherit character/word confidence scores from Tesseract.
- `method`: Extraction strategy identifier (`native_text`, `ocr`, `rule_based`, `pattern`, `human_correction`).
- `page_number`: 1-based page index indicating where the evidence token resides.
- `bounding_box`: Normalised or point coordinates `[x0, y0, x1, y1]` allowing visual highlighting on the rendered PDF preview.

---

## 4. Document-Level Processing Record

Each processed invoice yields an `InvoiceExtractionRecord`:

- `document_id`: Unique identifier (UUIDv4) generated upon initial ingestion.
- `file_name`: Original filename submitted by the user.
- `data`: Validated `InvoiceData` payload.
- `evidence`: Dictionary mapping field names to `FieldEvidence` objects.
- `validation_passed`: Boolean flag denoting whether all schema and business rules passed.
- `review_status`: State enumeration (`pending`, `approved`, `rejected`, `corrected`).
