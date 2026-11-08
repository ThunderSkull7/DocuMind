"""Deterministic, Decimal-based arithmetic validation for invoices.

Enforces arithmetic integrity across line items, subtotals, taxes, shipping,
discounts, and total amounts with configurable rounding tolerances without floating-point errors.
"""

from decimal import Decimal

from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.models import (
    Discrepancy,
    RuleCategory,
    Severity,
    ValidationOutcome,
)


class ArithmeticValidator:
    """Evaluates arithmetic consistency of extracted invoice figures."""

    def __init__(self, rounding_tolerance: Decimal = Decimal("0.02")) -> None:
        self.tolerance = rounding_tolerance

    def validate(self, record: InvoiceExtractionRecord) -> list[Discrepancy]:
        """Execute all arithmetic consistency rules against an extraction record."""
        discrepancies: list[Discrepancy] = []

        rf = record.raw_fields
        evidence = record.evidence
        doc_id = record.document_id

        subtotal: Decimal | None = rf.get("subtotal")
        tax: Decimal | None = rf.get("tax")
        total: Decimal | None = rf.get("total")
        shipping: Decimal | None = rf.get("shipping_amount")
        discount: Decimal | None = rf.get("discount_amount")
        amount_paid: Decimal | None = rf.get("amount_paid")
        balance_due: Decimal | None = rf.get("balance_due")
        tax_rate: Decimal | None = rf.get("tax_rate")
        line_items = rf.get("line_items", [])

        # -------------------------------------------------------------------------
        # ARITH_001: Line Item Calculation (Qty * Unit Price == Item Total)
        # -------------------------------------------------------------------------
        for idx, item in enumerate(line_items):
            item_num = idx + 1
            if item.quantity is not None and item.unit_price is not None:
                expected_line_total = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
                if item.total is not None:
                    diff = abs(expected_line_total - item.total)
                    if diff > self.tolerance:
                        discrepancies.append(
                            Discrepancy(
                                discrepancy_id=f"DISC-ARITH-001-{doc_id}-{item_num}",
                                document_id=doc_id,
                                rule_id="ARITH_001",
                                rule_name="Line Item Quantity x Price Consistency",
                                category=RuleCategory.ARITHMETIC,
                                severity=Severity.HIGH,
                                outcome=ValidationOutcome.FAIL,
                                affected_fields=["line_items"],
                                expected_value=expected_line_total,
                                actual_value=item.total,
                                difference=item.total - expected_line_total,
                                explanation=(
                                    f"Line item {item_num} ('{item.description}'): "
                                    f"Quantity ({item.quantity}) x Unit Price ({item.unit_price}) = "
                                    f"{expected_line_total}, but line total is stated as {item.total} "
                                    f"(difference: {item.total - expected_line_total})."
                                ),
                                evidence_references=["line_items"],
                                evidence_snippets=[item.bounding_box] if item.bounding_box else [],
                                review_recommendation="Inspect line item rate and quantity on original invoice preview.",
                            )
                        )
                else:
                    discrepancies.append(
                        Discrepancy(
                            discrepancy_id=f"DISC-ARITH-001-IND-{doc_id}-{item_num}",
                            document_id=doc_id,
                            rule_id="ARITH_001",
                            rule_name="Line Item Quantity x Price Consistency",
                            category=RuleCategory.ARITHMETIC,
                            severity=Severity.INFO,
                            outcome=ValidationOutcome.INDETERMINATE,
                            affected_fields=["line_items"],
                            expected_value=expected_line_total,
                            actual_value=None,
                            explanation=f"Line item {item_num} ('{item.description}') has no stated line total.",
                            review_recommendation="Verify whether line total was omitted from document table.",
                        )
                    )
            elif item.total is not None and (item.quantity is None or item.unit_price is None):
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-ARITH-001-PARTIAL-{doc_id}-{item_num}",
                        document_id=doc_id,
                        rule_id="ARITH_001",
                        rule_name="Line Item Quantity x Price Consistency",
                        category=RuleCategory.ARITHMETIC,
                        severity=Severity.INFO,
                        outcome=ValidationOutcome.INDETERMINATE,
                        affected_fields=["line_items"],
                        expected_value=None,
                        actual_value=item.total,
                        explanation=(
                            f"Line item {item_num} ('{item.description}') has stated total {item.total} "
                            "but quantity or unit price is unstated."
                        ),
                        review_recommendation="Verify whether unit price or quantity is standard flat rate.",
                    )
                )

        # -------------------------------------------------------------------------
        # ARITH_002: Line Items Sum vs Subtotal
        # -------------------------------------------------------------------------
        if line_items and subtotal is not None:
            if all(item.total is not None for item in line_items):
                calc_subtotal = sum((item.total for item in line_items), Decimal("0.00"))
                diff_sub = abs(calc_subtotal - subtotal)
                if diff_sub > self.tolerance:
                    discrepancies.append(
                        Discrepancy(
                            discrepancy_id=f"DISC-ARITH-002-{doc_id}",
                            document_id=doc_id,
                            rule_id="ARITH_002",
                            rule_name="Line Items Sum vs Subtotal",
                            category=RuleCategory.ARITHMETIC,
                            severity=Severity.HIGH,
                            outcome=ValidationOutcome.FAIL,
                            affected_fields=["subtotal", "line_items"],
                            expected_value=calc_subtotal,
                            actual_value=subtotal,
                            difference=subtotal - calc_subtotal,
                            explanation=(
                                f"Sum of {len(line_items)} line items equals {calc_subtotal}, "
                                f"which does not match stated subtotal {subtotal} "
                                f"(variance: {subtotal - calc_subtotal})."
                            ),
                            evidence_references=["subtotal", "line_items"],
                            evidence_snippets=[evidence[k] for k in ["subtotal"] if k in evidence],
                            review_recommendation="Check for unlisted fees, line discounts, or omitted line items.",
                        )
                    )
            else:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-ARITH-002-IND-{doc_id}",
                        document_id=doc_id,
                        rule_id="ARITH_002",
                        rule_name="Line Items Sum vs Subtotal",
                        category=RuleCategory.ARITHMETIC,
                        severity=Severity.LOW,
                        outcome=ValidationOutcome.INDETERMINATE,
                        affected_fields=["subtotal", "line_items"],
                        explanation="Cannot verify line items sum against subtotal because some line items lack totals.",
                        review_recommendation="Complete line item extraction or manual entry during review.",
                    )
                )

        # -------------------------------------------------------------------------
        # ARITH_003: Subtotal + Tax + Shipping - Discount == Total
        # -------------------------------------------------------------------------
        if subtotal is not None and total is not None:
            tax_val = tax if tax is not None else Decimal("0.00")
            ship_val = shipping if shipping is not None else Decimal("0.00")
            disc_val = discount if discount is not None else Decimal("0.00")

            expected_total = subtotal + tax_val + ship_val - disc_val
            diff_total = abs(expected_total - total)

            ev_refs = ["total", "subtotal"]
            if "tax" in evidence:
                ev_refs.append("tax")
            snippets = [evidence[k] for k in ev_refs if k in evidence]

            if diff_total > self.tolerance:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-ARITH-003-{doc_id}",
                        document_id=doc_id,
                        rule_id="ARITH_003",
                        rule_name="Invoice Total Arithmetic Consistency",
                        category=RuleCategory.ARITHMETIC,
                        severity=Severity.HIGH,
                        outcome=ValidationOutcome.FAIL,
                        affected_fields=["total", "subtotal", "tax"],
                        expected_value=expected_total,
                        actual_value=total,
                        difference=total - expected_total,
                        explanation=(
                            f"Calculated total (Subtotal {subtotal} + Tax {tax_val} + Shipping {ship_val} "
                            f"- Discount {disc_val} = {expected_total}) differs from printed total {total} "
                            f"by {total - expected_total} currency units."
                        ),
                        evidence_references=ev_refs,
                        evidence_snippets=snippets,
                        review_recommendation="Verify whether invoice contains unextracted surcharges or arithmetic errors.",
                    )
                )
        elif total is None:
            discrepancies.append(
                Discrepancy(
                    discrepancy_id=f"DISC-ARITH-003-IND-{doc_id}",
                    document_id=doc_id,
                    rule_id="ARITH_003",
                    rule_name="Invoice Total Arithmetic Consistency",
                    category=RuleCategory.ARITHMETIC,
                    severity=Severity.CRITICAL,
                    outcome=ValidationOutcome.INDETERMINATE,
                    affected_fields=["total"],
                    explanation="Invoice total is missing from document extraction; cannot verify arithmetic.",
                    review_recommendation="Locate total payable amount manually during human review.",
                )
            )

        # -------------------------------------------------------------------------
        # ARITH_004: Subtotal <= Total (in standard non-credit invoices)
        # -------------------------------------------------------------------------
        if subtotal is not None and total is not None and total > Decimal("0.00"):
            if subtotal > total + self.tolerance:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-ARITH-004-{doc_id}",
                        document_id=doc_id,
                        rule_id="ARITH_004",
                        rule_name="Subtotal Exceeds Total",
                        category=RuleCategory.ARITHMETIC,
                        severity=Severity.HIGH,
                        outcome=ValidationOutcome.FAIL,
                        affected_fields=["subtotal", "total"],
                        expected_value=total,
                        actual_value=subtotal,
                        difference=subtotal - total,
                        explanation=(
                            f"Stated subtotal ({subtotal}) is greater than stated total payable ({total}). "
                            "Unless large discounts apply, subtotal must not exceed total."
                        ),
                        evidence_references=["subtotal", "total"],
                        evidence_snippets=[
                            evidence[k] for k in ["subtotal", "total"] if k in evidence
                        ],
                        review_recommendation="Verify whether invoice is a credit note or has unextracted major discounts.",
                    )
                )

        # -------------------------------------------------------------------------
        # ARITH_005: Balance Due vs Total - Amount Paid
        # -------------------------------------------------------------------------
        if balance_due is not None and amount_paid is not None and total is not None:
            expected_balance = total - amount_paid
            if abs(expected_balance - balance_due) > self.tolerance:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-ARITH-005-{doc_id}",
                        document_id=doc_id,
                        rule_id="ARITH_005",
                        rule_name="Balance Due Calculation",
                        category=RuleCategory.ARITHMETIC,
                        severity=Severity.MEDIUM,
                        outcome=ValidationOutcome.FAIL,
                        affected_fields=["balance_due", "amount_paid", "total"],
                        expected_value=expected_balance,
                        actual_value=balance_due,
                        difference=balance_due - expected_balance,
                        explanation=(
                            f"Balance due ({balance_due}) does not equal Total ({total}) - "
                            f"Amount Paid ({amount_paid}) = {expected_balance}."
                        ),
                        review_recommendation="Verify payment history and balance due in accounts payable.",
                    )
                )

        # -------------------------------------------------------------------------
        # ARITH_006: Stated Tax Rate Calculation
        # -------------------------------------------------------------------------
        if tax_rate is not None and subtotal is not None and tax is not None:
            expected_tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
            if abs(expected_tax - tax) > self.tolerance:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-ARITH-006-{doc_id}",
                        document_id=doc_id,
                        rule_id="ARITH_006",
                        rule_name="Stated Tax Rate Application",
                        category=RuleCategory.ARITHMETIC,
                        severity=Severity.MEDIUM,
                        outcome=ValidationOutcome.FAIL,
                        affected_fields=["tax", "tax_rate", "subtotal"],
                        expected_value=expected_tax,
                        actual_value=tax,
                        difference=tax - expected_tax,
                        explanation=(
                            f"Stated tax rate of {tax_rate * 100}% on subtotal {subtotal} yields "
                            f"{expected_tax}, which differs from stated tax {tax}."
                        ),
                        review_recommendation="Check if non-taxable items are mixed into the subtotal.",
                    )
                )

        return discrepancies
