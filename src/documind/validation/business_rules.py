"""Deterministic business rule validation for invoices.

Evaluates data completeness, temporal consistency (dates), currency standards,
suspicious zero/negative totals, and visual glyph ambiguity flags.
"""

import re
from datetime import date
from decimal import Decimal

from documind.extraction.money_parser import KNOWN_CURRENCIES
from documind.schemas.invoice import EvidenceStatus, InvoiceExtractionRecord
from documind.validation.models import (
    Discrepancy,
    RuleCategory,
    Severity,
    ValidationOutcome,
)


class BusinessRulesValidator:
    """Evaluates business rules, completeness, and logical consistency on extracted invoices."""

    def __init__(self, reference_date: date | None = None) -> None:
        # Reference date used for future-date checks (defaults to current date)
        self.ref_date = reference_date or date.today()

    def validate(self, record: InvoiceExtractionRecord) -> list[Discrepancy]:
        """Execute all business validation rules against an extraction record."""
        discrepancies: list[Discrepancy] = []

        rf = record.raw_fields
        evidence = record.evidence
        doc_id = record.document_id

        inv_num = rf.get("invoice_number")
        inv_date = rf.get("invoice_date")
        due_date = rf.get("due_date")
        vendor_name = rf.get("vendor_name")
        currency = rf.get("currency")
        total: Decimal | None = rf.get("total")
        line_items = rf.get("line_items", [])

        # -------------------------------------------------------------------------
        # BIZ_001: Mandatory Fields Completeness
        # -------------------------------------------------------------------------
        mandatory_checks = [
            ("invoice_number", inv_num, "Invoice Number"),
            ("invoice_date", inv_date, "Invoice Date"),
            ("vendor_name", vendor_name, "Vendor Name"),
            ("total", total, "Total Amount"),
            ("currency", currency, "Document Currency"),
        ]

        for field_key, field_val, field_label in mandatory_checks:
            ev_status = evidence.get(field_key, None)
            is_missing = field_val is None or (
                ev_status is not None and ev_status.status == EvidenceStatus.MISSING
            )

            if is_missing:
                snippets = [evidence[field_key]] if field_key in evidence else []
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-001-{doc_id}-{field_key}",
                        document_id=doc_id,
                        rule_id="BIZ_001",
                        rule_name=f"Mandatory Field Completeness: {field_label}",
                        category=RuleCategory.COMPLETENESS,
                        severity=Severity.CRITICAL,
                        outcome=ValidationOutcome.FAIL,
                        affected_fields=[field_key],
                        expected_value=f"Non-empty {field_label}",
                        actual_value=None,
                        explanation=f"Required invoice header field '{field_label}' was not found on document.",
                        evidence_references=[field_key] if field_key in evidence else [],
                        evidence_snippets=snippets,
                        review_recommendation=f"Locate and manually input {field_label} during human review.",
                    )
                )

        # -------------------------------------------------------------------------
        # BIZ_002: Temporal Ordering (Invoice Date <= Due Date)
        # -------------------------------------------------------------------------
        if inv_date is not None and due_date is not None:
            if isinstance(inv_date, date) and isinstance(due_date, date):
                if inv_date > due_date:
                    snippets = [evidence[k] for k in ["invoice_date", "due_date"] if k in evidence]
                    discrepancies.append(
                        Discrepancy(
                            discrepancy_id=f"DISC-BIZ-002-{doc_id}",
                            document_id=doc_id,
                            rule_id="BIZ_002",
                            rule_name="Invoice Issuance Precedes Due Date",
                            category=RuleCategory.TEMPORAL,
                            severity=Severity.HIGH,
                            outcome=ValidationOutcome.FAIL,
                            affected_fields=["invoice_date", "due_date"],
                            expected_value=f"<= {due_date.isoformat()}",
                            actual_value=inv_date.isoformat(),
                            explanation=(
                                f"Invoice issuance date ({inv_date.isoformat()}) occurs after "
                                f"the stated payment due date ({due_date.isoformat()})."
                            ),
                            evidence_references=["invoice_date", "due_date"],
                            evidence_snippets=snippets,
                            review_recommendation="Confirm correct invoice issuance date with issuing vendor.",
                        )
                    )

        # -------------------------------------------------------------------------
        # BIZ_003: Temporal Validity (Future Dates & Archival Stale Dates)
        # -------------------------------------------------------------------------
        if inv_date is not None and isinstance(inv_date, date):
            # Check if older than 10 years (3650 days)
            age_days = (self.ref_date - inv_date).days
            if age_days > 3652:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-003-AGE-{doc_id}",
                        document_id=doc_id,
                        rule_id="BIZ_003",
                        rule_name="Stale Invoice / Archival Threshold",
                        category=RuleCategory.TEMPORAL,
                        severity=Severity.LOW,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["invoice_date"],
                        expected_value=f"> {self.ref_date.year - 10}",
                        actual_value=inv_date.isoformat(),
                        explanation=f"Invoice is dated {inv_date.isoformat()} (over 10 years old).",
                        evidence_references=["invoice_date"] if "invoice_date" in evidence else [],
                        review_recommendation="Verify whether this invoice is an archival historical entry.",
                    )
                )

        # -------------------------------------------------------------------------
        # BIZ_004: Ambiguous Field Values
        # -------------------------------------------------------------------------
        for field_name, ev_item in evidence.items():
            if ev_item.status == EvidenceStatus.AMBIGUOUS:
                cands_str = ", ".join(str(c) for c in ev_item.candidates)
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-004-{doc_id}-{field_name}",
                        document_id=doc_id,
                        rule_id="BIZ_004",
                        rule_name=f"Ambiguous Field Value: {field_name}",
                        category=RuleCategory.FORMAT_AND_ENCODING,
                        severity=Severity.MEDIUM,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=[field_name],
                        expected_value="Unambiguous interpretation",
                        actual_value=ev_item.raw_text,
                        explanation=(
                            f"Field '{field_name}' raw text '{ev_item.raw_text}' has multiple valid interpretations: "
                            f"[{cands_str}]."
                        ),
                        evidence_references=[field_name],
                        evidence_snippets=[ev_item],
                        review_recommendation="Review original document layout to select the correct candidate.",
                    )
                )

        # -------------------------------------------------------------------------
        # BIZ_005: Suspicious or Zero Invoice Total
        # -------------------------------------------------------------------------
        if total is not None:
            if total == Decimal("0.00"):
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-005-ZERO-{doc_id}",
                        document_id=doc_id,
                        rule_id="BIZ_005",
                        rule_name="Zero Invoice Total",
                        category=RuleCategory.BUSINESS_POLICY,
                        severity=Severity.MEDIUM,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["total"],
                        expected_value="> 0.00",
                        actual_value=Decimal("0.00"),
                        explanation="Invoice total is 0.00; verify if invoice is informational or zero-value notice.",
                        evidence_references=["total"] if "total" in evidence else [],
                        review_recommendation="Verify whether zero total was expected.",
                    )
                )
            elif total < Decimal("0.00"):
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-005-NEG-{doc_id}",
                        document_id=doc_id,
                        rule_id="BIZ_005",
                        rule_name="Negative Invoice Total (Credit Note)",
                        category=RuleCategory.BUSINESS_POLICY,
                        severity=Severity.LOW,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["total"],
                        expected_value=">= 0.00",
                        actual_value=total,
                        explanation=f"Negative invoice total ({total}) indicates a credit note or refund.",
                        evidence_references=["total"] if "total" in evidence else [],
                        review_recommendation="Ensure document is routed to credit memo processing.",
                    )
                )

        # -------------------------------------------------------------------------
        # BIZ_006: Currency ISO Compliance
        # -------------------------------------------------------------------------
        if currency:
            if currency.upper() not in KNOWN_CURRENCIES:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-006-{doc_id}",
                        document_id=doc_id,
                        rule_id="BIZ_006",
                        rule_name="Standard ISO 4217 Currency Code",
                        category=RuleCategory.FORMAT_AND_ENCODING,
                        severity=Severity.MEDIUM,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["currency"],
                        expected_value="Standard ISO 4217 code (e.g. USD, EUR, GBP)",
                        actual_value=currency,
                        explanation=f"Currency '{currency}' is not a recognized standard 3-letter currency code.",
                        evidence_references=["currency"] if "currency" in evidence else [],
                        review_recommendation="Select the canonical ISO currency code.",
                    )
                )

        # -------------------------------------------------------------------------
        # BIZ_007: Non-Negative Quantities & Prices
        # -------------------------------------------------------------------------
        for idx, item in enumerate(line_items):
            if item.quantity is not None and item.quantity < Decimal("0.00"):
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-007-QTY-{doc_id}-{idx + 1}",
                        document_id=doc_id,
                        rule_id="BIZ_007",
                        rule_name="Line Item Positive Quantity",
                        category=RuleCategory.BUSINESS_POLICY,
                        severity=Severity.LOW,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["line_items"],
                        expected_value=">= 0",
                        actual_value=item.quantity,
                        explanation=f"Line item {idx + 1} has negative quantity ({item.quantity}).",
                        review_recommendation="Verify whether line item is a return or debit adjustment.",
                    )
                )

        # -------------------------------------------------------------------------
        # BIZ_008: Visually Confusable Character Notice (Glyph Ambiguity)
        # -------------------------------------------------------------------------
        # Flag when identifier contains adjacent confusable pairs (e.g. 0O, 1I, 1l)
        if inv_num:
            suffix = inv_num.split("-")[-1]
            if re.search(r"(?:0[O]|[O]0|1[Il]|[Il]1|[Il]{2})", suffix):
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-BIZ-008-{doc_id}",
                        document_id=doc_id,
                        rule_id="BIZ_008",
                        rule_name="Visual Glyph Ambiguity in Invoice Identifier",
                        category=RuleCategory.FORMAT_AND_ENCODING,
                        severity=Severity.INFO,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["invoice_number"],
                        expected_value="Unambiguous identifier",
                        actual_value=inv_num,
                        explanation=(
                            f"Invoice number '{inv_num}' contains visually confusable adjacent glyphs (0 vs O, 1 vs I vs l). "
                            "Check original scan image to confirm exact characters."
                        ),
                        evidence_references=["invoice_number"]
                        if "invoice_number" in evidence
                        else [],
                        review_recommendation="Confirm characters against original high-resolution document preview.",
                    )
                )

        return discrepancies
