# DocuMind Invoice Document Schema Specification

This document defines the formal schema, data types, validation constraints, and evidence metadata standards for invoices processed by DocuMind.

---

## 1. Core and Extended Invoice Fields

### 1.1 Identification Fields
| Field Name | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `invoice_number` | `str` | **Required** | Unique identifier assigned by the vendor (1–100 chars). |
| `invoice_date` | `date` | **Required** | Date invoice was issued (ISO 8601). |
| `due_date` | `date` | *Optional* | Date payment is due. |
| `purchase_order_number` | `str` | *Optional* | Associated purchase order number. |
| `currency` | `str` | **Required** | ISO 4217 3-letter currency code (`USD`, `EUR`, `GBP`). |

### 1.2 Vendor Profile Fields
| Field Name | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `vendor_name` | `str` | **Required** | Legal corporate or trading name of billing entity (1–200 chars). |
| `vendor_address` | `str` | *Optional* | Physical or registered corporate address. |
| `vendor_email` | `str` | *Optional* | Vendor billing contact email. |
| `vendor_phone` | `str` | *Optional* | Vendor phone number. |
| `vendor_tax_id` | `str` | *Optional* | Tax, VAT, or corporate identifier (`US-EIN-...`, `DE-VAT-...`). |

### 1.3 Customer Profile Fields
| Field Name | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `customer_name` | `str` | *Optional* | Customer or Bill-To corporate entity name. |
| `customer_address` | `str` | *Optional* | Customer billing or delivery address. |
| `customer_email` | `str` | *Optional* | Customer contact email. |
| `customer_tax_id` | `str` | *Optional* | Customer tax/VAT registration identifier. |

### 1.4 Financial Summary Fields
| Field Name | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `subtotal` | `Decimal` | *Optional* | Net billable sum prior to applicable taxes and fees. |
| `tax` | `Decimal` | *Optional* | Aggregated tax, VAT, or GST applied to invoice. |
| `tax_rate` | `Decimal` | *Optional* | Explicit tax percentage applied (e.g. 0.10 for 10%). |
| `discount_amount` | `Decimal` | *Optional* | Discount amount subtracted from total. |
| `shipping_amount` | `Decimal` | *Optional* | Freight, shipping, or dispatch fee. |
| `total` | `Decimal` | **Required** | Final gross amount payable. |
| `amount_paid` | `Decimal` | *Optional* | Amount prepaid or already credited. |
| `balance_due` | `Decimal` | *Optional* | Outstanding balance payable. |

### 1.5 Line-Item Fields
Structured line items represented by `InvoiceLineItem`:
- `description`: Item or service description (`str`, required, min length 1).
- `quantity`: Billed quantity or hours (`Decimal | None`).
- `unit_of_measure`: Measurement unit if explicit (`str | None`).
- `unit_price`: Rate or unit price (`Decimal | None`).
- `discount`: Line-level discount (`Decimal | None`).
- `tax`: Line-level tax (`Decimal | None`).
- `total`: Extended line total (`Decimal | None`).
- `bounding_box`: Spatial bounding box spanning the table row (`BoundingBox | None`).
- `page_number`: 1-based index where line item was identified (`int | None`).
- `confidence`: Heuristic extraction confidence score (`float`).
- `status`: Row status (`"extracted"`, `"ambiguous"`, `"needs_review"`).

---

## 2. Validation & Business Rules

### 2.1 Syntactic Schema Validation (Phase 4 Implemented)
- **Non-empty Constraints**: Required fields (`invoice_number`, `vendor_name`, `currency`) must not be empty or solely whitespace.
- **Date Parsability**: Dates parse into standard `datetime.date` objects.
- **Monetary Precision**: All numeric amounts parse into fixed-point `Decimal` instances to avoid floating-point inaccuracies.
- **Negative Negative Case Handling**: Deliberately omitted required fields (e.g. `DOC-SYN-007` missing `invoice_number`, `DOC-SYN-018` missing `vendor_name`) fail schema validation and transition the record to `review_status="needs_review"`.

### 2.2 Semantic & Arithmetic Business Rules (Phase 5)
1. **Total Consistency Rule**: $\text{subtotal} + \text{tax} = \text{total}$ within $\pm 0.02$ tolerance.
2. **Subtotal vs Total**: $\text{subtotal} \le \text{total}$ (unless credit adjustment applied).
3. **Temporal Validity**: Issuance date must not be in the future beyond timezone grace periods.
4. **Currency Standardization**: Currency symbols mapped to canonical ISO 4217 codes.

---

## 3. Evidence Grounding & Provenance Metadata

Every extracted value is linked to a `FieldEvidence` record containing:

```json
{
  "field_name": "invoice_number",
  "extracted_value": "INV-2024-0001",
  "raw_text": "INV-2024-0001",
  "confidence": 1.0,
  "method": "rule_based",
  "source_method": "native_text",
  "ocr_confidence": null,
  "status": "extracted",
  "page_number": 1,
  "bounding_box": {
    "page": 1,
    "x0": 408.3,
    "y0": 110.4,
    "x1": 479.6,
    "y1": 119.0
  },
  "candidates": [],
  "warnings": []
}
```

### Evidence Status Taxonomy
- `extracted`: Successfully located and parsed with reliable evidence.
- `missing`: Explicitly omitted or absent from the document (e.g. `[Invoice Number: NOT SPECIFIED]`).
- `ambiguous`: Multiple competing candidate interpretations exist (e.g. date format `03/04/2024`).
- `needs_review`: Extraction uncertain, requiring human review.

---

## 4. Document-Level Processing Record

Each processed invoice yields an `InvoiceExtractionRecord`:

- `document_id`: Unique identifier (e.g., `DOC-SYN-001`).
- `file_name`: Original document filename.
- `data`: Validated `InvoiceData` payload (or `None` if schema validation failed).
- `raw_fields`: Dictionary of raw extracted fields prior to validation.
- `evidence`: Dictionary mapping field names to `FieldEvidence` objects.
- `validation_passed`: Boolean flag denoting whether schema validation succeeded.
- `validation_errors`: Detailed list of Pydantic validation errors if validation failed.
- `review_status`: State enumeration (`approved`, `needs_review`, `pending`, `rejected`, `corrected`).
- `warnings`: Document-level non-fatal extraction warnings.
