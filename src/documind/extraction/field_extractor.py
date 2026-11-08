"""Structured invoice field extractor and evidence mapping engine.

Transforms page-level hybrid extraction output (native text and Tesseract OCR)
into validated, machine-readable invoice records with end-to-end evidence grounding.
"""

import re
from typing import Any

from pydantic import ValidationError

from documind.extraction.date_parser import parse_invoice_date
from documind.extraction.evidence_mapper import EvidenceMapper
from documind.extraction.line_item_extractor import LineItemExtractor
from documind.extraction.models import ExtractionResult, SpatialWord
from documind.extraction.money_parser import parse_monetary_value
from documind.extraction.patterns import (
    DUE_DATE_LABELS,
    INVOICE_DATE_LABELS,
    INVOICE_NUMBER_LABELS,
    PO_NUMBER_LABELS,
    SUBTOTAL_LABELS,
    TAX_LABELS,
    TOTAL_LABELS,
)
from documind.extraction.spatial import (
    SpatialLine,
    cluster_words_into_lines,
)
from documind.extraction.vendor_extractor import EntityExtractor
from documind.schemas.invoice import (
    EvidenceStatus,
    ExtractionMethod,
    FieldEvidence,
    InvoiceData,
    InvoiceExtractionRecord,
)


class StructuredInvoiceExtractor:
    """Extracts structured invoice fields, financial summaries, entities, and line items."""

    def __init__(self) -> None:
        self.entity_extractor = EntityExtractor()
        self.line_item_extractor = LineItemExtractor()

    def extract(
        self,
        extraction_result: ExtractionResult,
        file_name: str = "document.pdf",
    ) -> InvoiceExtractionRecord:
        """Extract all structured fields from ExtractionResult into an InvoiceExtractionRecord.

        Args:
            extraction_result: Page-aware output from ExtractionService.
            file_name: Original document filename.

        Returns:
            InvoiceExtractionRecord with validated InvoiceData, evidence map, and errors.
        """
        raw_fields: dict[str, Any] = {}
        evidence: dict[str, FieldEvidence] = {}
        warnings: list[str] = list(extraction_result.warnings)

        # 1. Cluster words into spatial lines for every page
        page_lines: dict[int, list[SpatialLine]] = {}
        all_lines: list[SpatialLine] = []

        for p in extraction_result.pages:
            words = [w for b in p.text_blocks for w in b.words]
            lines = cluster_words_into_lines(words)
            page_lines[p.page_number] = lines
            all_lines.extend(lines)

        first_page_lines = page_lines.get(1, [])

        # 2. Extract Vendor & Customer Information
        vendor_info = self.entity_extractor.extract_vendor_info(first_page_lines, page_number=1)
        for k, (val, ev) in vendor_info.items():
            raw_fields[k] = val
            evidence[k] = ev

        customer_info = self.entity_extractor.extract_customer_info(first_page_lines, page_number=1)
        for k, (val, ev) in customer_info.items():
            raw_fields[k] = val
            evidence[k] = ev

        # 3. Extract Invoice Number
        inv_num_val, inv_num_ev = self._extract_invoice_number(all_lines)
        raw_fields["invoice_number"] = inv_num_val
        evidence["invoice_number"] = inv_num_ev

        # 4. Extract Invoice Date
        inv_date_val, inv_date_ev = self._extract_invoice_date(all_lines)
        raw_fields["invoice_date"] = inv_date_val
        evidence["invoice_date"] = inv_date_ev

        # 5. Extract Due Date
        due_date_val, due_date_ev = self._extract_due_date(all_lines)
        raw_fields["due_date"] = due_date_val
        evidence["due_date"] = due_date_ev

        # 6. Extract Purchase Order Number if present
        po_val, po_ev = self._extract_po_number(all_lines)
        if po_val:
            raw_fields["purchase_order_number"] = po_val
            evidence["purchase_order_number"] = po_ev

        # 7. Extract Totals (Subtotal, Tax, Total, Currency)
        financial_info = self._extract_financial_summary(all_lines)
        for k, (val, ev) in financial_info.items():
            raw_fields[k] = val
            evidence[k] = ev

        # 8. Extract Line Items
        line_items = self.line_item_extractor.extract_line_items_from_pages(extraction_result.pages)
        raw_fields["line_items"] = line_items

        # 9. Perform Pydantic Schema Validation
        validation_passed = False
        validation_errors: list[str] = []
        invoice_data: InvoiceData | None = None

        # Build candidate dictionary for InvoiceData
        candidate_data: dict[str, Any] = {
            "invoice_number": raw_fields.get("invoice_number"),
            "invoice_date": raw_fields.get("invoice_date"),
            "vendor_name": raw_fields.get("vendor_name"),
            "currency": raw_fields.get("currency") or "USD",
            "total": raw_fields.get("total"),
            "subtotal": raw_fields.get("subtotal"),
            "tax": raw_fields.get("tax"),
            "due_date": raw_fields.get("due_date"),
            "purchase_order_number": raw_fields.get("purchase_order_number"),
            "vendor_address": raw_fields.get("vendor_address"),
            "vendor_email": raw_fields.get("vendor_email"),
            "vendor_phone": raw_fields.get("vendor_phone"),
            "vendor_tax_id": raw_fields.get("vendor_tax_id"),
            "customer_name": raw_fields.get("customer_name"),
            "customer_address": raw_fields.get("customer_address"),
            "customer_email": raw_fields.get("customer_email"),
            "customer_tax_id": raw_fields.get("customer_tax_id"),
            "tax_rate": raw_fields.get("tax_rate"),
            "discount_amount": raw_fields.get("discount_amount"),
            "shipping_amount": raw_fields.get("shipping_amount"),
            "amount_paid": raw_fields.get("amount_paid"),
            "balance_due": raw_fields.get("balance_due"),
            "line_items": line_items,
        }

        # Filter out None values that are optional to ensure clean validation
        clean_candidate = {k: v for k, v in candidate_data.items() if v is not None}

        try:
            invoice_data = InvoiceData(**clean_candidate)
            validation_passed = True
        except ValidationError as val_err:
            validation_passed = False
            for err in val_err.errors():
                loc_str = " -> ".join(str(loc) for loc in err["loc"])
                validation_errors.append(f"{loc_str}: {err['msg']}")

        review_status = "approved" if validation_passed else "needs_review"

        return InvoiceExtractionRecord(
            document_id=extraction_result.document_id,
            file_name=file_name,
            data=invoice_data,
            raw_fields=raw_fields,
            evidence=evidence,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            review_status=review_status,
            warnings=warnings,
        )

    def _extract_invoice_number(
        self,
        lines: list[SpatialLine],
    ) -> tuple[str | None, FieldEvidence]:
        """Extract invoice identification number with negative case detection."""
        for line in lines:
            l_lower = line.text.lower()
            if "internal id:" in l_lower and "corpus" in l_lower:
                continue  # Skip footer template metadata

            for label in INVOICE_NUMBER_LABELS:
                if label in l_lower:
                    idx = l_lower.find(label)
                    after_text = line.text[idx + len(label) :].strip()

                    # Check for explicit omitted marker
                    if (
                        "not specified" in after_text.lower()
                        or "missing" in after_text.lower()
                        or not after_text
                    ):
                        return (
                            None,
                            EvidenceMapper.create_missing_evidence(
                                field_name="invoice_number",
                                reason="Invoice number explicitly omitted or not specified",
                                raw_text=line.text,
                            ),
                        )

                    # Extract first token after label
                    tokens = after_text.split()
                    inv_candidate = tokens[0].strip(":,;[]()")

                    # Collect spatial words for the candidate token
                    val_words: list[SpatialWord] = []
                    for w in line.words:
                        if inv_candidate in w.text or w.text in inv_candidate:
                            val_words.append(w)

                    return (
                        inv_candidate,
                        EvidenceMapper.create_from_words(
                            field_name="invoice_number",
                            extracted_value=inv_candidate,
                            words=val_words or line.words,
                            page_number=line.page_number,
                            raw_text=inv_candidate,
                            method=ExtractionMethod.RULE_BASED,
                        ),
                    )

        # Fallback regex search for INV- pattern
        for line in lines:
            if "internal id:" in line.text.lower():
                continue
            match = re.search(r"\b(INV-[A-Za-z0-9_-]{4,20})\b", line.text)
            if match:
                cand = match.group(1)
                val_words = [w for w in line.words if cand in w.text]
                return (
                    cand,
                    EvidenceMapper.create_from_words(
                        field_name="invoice_number",
                        extracted_value=cand,
                        words=val_words or line.words,
                        page_number=line.page_number,
                        raw_text=cand,
                        method=ExtractionMethod.PATTERN,
                    ),
                )

        return (
            None,
            EvidenceMapper.create_missing_evidence(
                field_name="invoice_number",
                reason="Invoice number label not located on document",
            ),
        )

    def _extract_invoice_date(
        self,
        lines: list[SpatialLine],
    ) -> tuple[Any, FieldEvidence]:
        """Extract invoice issuance date with strict ambiguity preservation."""
        for line in lines:
            l_lower = line.text.lower()
            if "due date" in l_lower:
                continue  # Handled separately

            for label in INVOICE_DATE_LABELS:
                if label in l_lower:
                    idx = l_lower.find(label)
                    after_text = line.text[idx + len(label) :].strip()
                    tokens = after_text.split()
                    if not tokens:
                        continue

                    cand_text = tokens[0].strip(":,;[]()")
                    parse_res = parse_invoice_date(cand_text)

                    # Identify constituent words
                    val_words = [
                        w for w in line.words if cand_text in w.text or w.text in cand_text
                    ]

                    if parse_res.is_ambiguous:
                        return (
                            parse_res.parsed_date,
                            EvidenceMapper.create_from_words(
                                field_name="invoice_date",
                                extracted_value=parse_res.parsed_date,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=cand_text,
                                method=ExtractionMethod.PATTERN,
                                status=EvidenceStatus.AMBIGUOUS,
                                candidates=[d.isoformat() for d in parse_res.candidate_dates],
                                confidence=0.5,
                                warnings=[
                                    f"Ambiguous date format '{cand_text}'. "
                                    f"Candidates: {[d.isoformat() for d in parse_res.candidate_dates]}"
                                ],
                            ),
                        )
                    elif parse_res.parsed_date is not None:
                        return (
                            parse_res.parsed_date,
                            EvidenceMapper.create_from_words(
                                field_name="invoice_date",
                                extracted_value=parse_res.parsed_date,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=cand_text,
                                method=ExtractionMethod.RULE_BASED,
                                status=EvidenceStatus.EXTRACTED,
                                confidence=1.0,
                            ),
                        )

        return (
            None,
            EvidenceMapper.create_missing_evidence(
                field_name="invoice_date",
                reason="Invoice date label not located on document",
            ),
        )

    def _extract_due_date(
        self,
        lines: list[SpatialLine],
    ) -> tuple[Any, FieldEvidence]:
        """Extract payment due date."""
        for line in lines:
            l_lower = line.text.lower()
            for label in DUE_DATE_LABELS:
                if label in l_lower:
                    idx = l_lower.find(label)
                    after_text = line.text[idx + len(label) :].strip()
                    tokens = after_text.split()
                    if not tokens:
                        continue
                    cand_text = tokens[0].strip(":,;[]()")
                    parse_res = parse_invoice_date(cand_text)
                    val_words = [
                        w for w in line.words if cand_text in w.text or w.text in cand_text
                    ]

                    if parse_res.parsed_date:
                        return (
                            parse_res.parsed_date,
                            EvidenceMapper.create_from_words(
                                field_name="due_date",
                                extracted_value=parse_res.parsed_date,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=cand_text,
                                method=ExtractionMethod.RULE_BASED,
                            ),
                        )

        return (
            None,
            EvidenceMapper.create_missing_evidence(
                field_name="due_date",
                reason="Due date not present on document",
            ),
        )

    def _extract_po_number(
        self,
        lines: list[SpatialLine],
    ) -> tuple[str | None, FieldEvidence]:
        """Extract purchase order number if specified."""
        for line in lines:
            l_lower = line.text.lower()
            for label in PO_NUMBER_LABELS:
                if label in l_lower:
                    idx = l_lower.find(label)
                    after_text = line.text[idx + len(label) :].strip()
                    tokens = after_text.split()
                    if tokens:
                        cand = tokens[0].strip(":,;[]()")
                        val_words = [w for w in line.words if cand in w.text]
                        return (
                            cand,
                            EvidenceMapper.create_from_words(
                                field_name="purchase_order_number",
                                extracted_value=cand,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=cand,
                            ),
                        )
        return (None, EvidenceMapper.create_missing_evidence("purchase_order_number"))

    def _extract_financial_summary(
        self,
        lines: list[SpatialLine],
    ) -> dict[str, tuple[Any, FieldEvidence]]:
        """Extract subtotal, tax, total, and document currency."""
        results: dict[str, tuple[Any, FieldEvidence]] = {}
        detected_currency: str | None = None
        curr_words: list[SpatialWord] = []

        # 1. Subtotal
        for line in lines:
            l_lower = line.text.lower()
            for label in SUBTOTAL_LABELS:
                if label in l_lower:
                    idx = l_lower.find(label)
                    after_text = line.text[idx + len(label) :].strip()
                    money_res = parse_monetary_value(after_text)
                    if money_res.is_valid and money_res.amount is not None:
                        val_words = [w for w in line.words if w.bounding_box.x0 >= 350.0]
                        results["subtotal"] = (
                            money_res.amount,
                            EvidenceMapper.create_from_words(
                                field_name="subtotal",
                                extracted_value=money_res.amount,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=after_text,
                            ),
                        )
                        if money_res.currency and not detected_currency:
                            detected_currency = money_res.currency
                            curr_words = [w for w in line.words if money_res.currency in w.text]
                        break

        # 2. Tax / VAT
        for line in lines:
            l_lower = line.text.lower()
            # Avoid matching lines where 'tax' is part of Tax ID or other label
            if any(k in l_lower for k in ["tax/vat id", "tax id", "tax registration"]):
                continue

            for label in TAX_LABELS:
                if label in l_lower:
                    idx = l_lower.find(label)
                    after_text = line.text[idx + len(label) :].strip()

                    # Handle EXEMPT
                    if "exempt" in after_text.lower():
                        val_words = [w for w in line.words if w.bounding_box.x0 >= 350.0]
                        results["tax"] = (
                            None,
                            EvidenceMapper.create_from_words(
                                field_name="tax",
                                extracted_value=None,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=after_text,
                                status=EvidenceStatus.EXTRACTED,
                                warnings=["Tax is exempt or zero"],
                            ),
                        )
                        break

                    money_res = parse_monetary_value(after_text)
                    if money_res.is_valid and money_res.amount is not None:
                        val_words = [w for w in line.words if w.bounding_box.x0 >= 350.0]
                        results["tax"] = (
                            money_res.amount,
                            EvidenceMapper.create_from_words(
                                field_name="tax",
                                extracted_value=money_res.amount,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=after_text,
                            ),
                        )
                        if money_res.currency and not detected_currency:
                            detected_currency = money_res.currency
                            curr_words = [w for w in line.words if money_res.currency in w.text]
                        break

        if "tax" not in results:
            results["tax"] = (
                None,
                EvidenceMapper.create_missing_evidence(
                    field_name="tax",
                    reason="Tax amount omitted or exempt",
                ),
            )

        # 3. Total
        for line in lines:
            l_lower = line.text.lower()
            # Must not match subtotal or net total
            if "subtotal" in l_lower or "net total" in l_lower:
                continue

            for label in TOTAL_LABELS:
                if label in l_lower:
                    idx = l_lower.find(label)
                    after_text = line.text[idx + len(label) :].strip()
                    money_res = parse_monetary_value(after_text)
                    if money_res.is_valid and money_res.amount is not None:
                        val_words = [w for w in line.words if w.bounding_box.x0 >= 350.0]
                        results["total"] = (
                            money_res.amount,
                            EvidenceMapper.create_from_words(
                                field_name="total",
                                extracted_value=money_res.amount,
                                words=val_words or line.words,
                                page_number=line.page_number,
                                raw_text=after_text,
                            ),
                        )
                        if money_res.currency:
                            detected_currency = money_res.currency
                            curr_words = [w for w in line.words if money_res.currency in w.text]
                        break

        # 4. Currency
        final_currency = detected_currency or "USD"
        results["currency"] = (
            final_currency,
            EvidenceMapper.create_from_words(
                field_name="currency",
                extracted_value=final_currency,
                words=curr_words or (lines[0].words if lines else []),
                page_number=lines[0].page_number if lines else 1,
                raw_text=final_currency,
                method=ExtractionMethod.RULE_BASED,
            ),
        )

        return results
