"""Reconciliation engine matching extracted invoice entities against reference records.

Supports optional matching against vendor master catalogs and purchase orders,
identifying exact matches, partial matches, and PO value conflicts deterministically.
"""

import difflib
from decimal import Decimal

from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.duplicate_detection import normalize_vendor_for_matching
from documind.validation.models import (
    Discrepancy,
    PurchaseOrderReference,
    ReferenceMatchResult,
    ReferenceMatchStatus,
    RuleCategory,
    Severity,
    ValidationOutcome,
    VendorMasterRecord,
)


class ReferenceMatcher:
    """Reconciles extracted invoice data against optional reference master catalogs."""

    def __init__(
        self,
        vendor_master: list[VendorMasterRecord] | None = None,
        po_database: list[PurchaseOrderReference] | None = None,
    ) -> None:
        self.vendors = vendor_master or []
        self.po_records = po_database or []

    def match(
        self, record: InvoiceExtractionRecord
    ) -> tuple[ReferenceMatchResult, list[Discrepancy]]:
        """Reconcile extracted invoice data against registered vendor master and PO records."""
        discrepancies: list[Discrepancy] = []
        doc_id = record.document_id
        rf = record.raw_fields

        vendor_name = rf.get("vendor_name")
        vendor_tax_id = rf.get("vendor_tax_id")
        po_number = rf.get("purchase_order_number")
        total: Decimal | None = rf.get("total")
        currency = rf.get("currency")

        v_status = ReferenceMatchStatus.NOT_PROVIDED
        matched_v_id: str | None = None
        v_details = "No vendor master supplied"

        # 1. Match against Vendor Master Data
        if self.vendors:
            v_status = ReferenceMatchStatus.NOT_FOUND
            v_details = f"Vendor '{vendor_name}' not found in vendor master catalog"
            norm_ext_vendor = normalize_vendor_for_matching(vendor_name)

            best_sim = 0.0
            best_vendor: VendorMasterRecord | None = None

            for v in self.vendors:
                # Direct name match
                if vendor_name and v.name.lower() == vendor_name.lower():
                    v_status = ReferenceMatchStatus.EXACT
                    matched_v_id = v.vendor_id
                    v_details = f"Exact match with Vendor Master: {v.vendor_id} ({v.name})"
                    best_vendor = v
                    break

                # Direct Tax ID match
                if vendor_tax_id and v.tax_id and vendor_tax_id.strip() == v.tax_id.strip():
                    v_status = ReferenceMatchStatus.EXACT
                    matched_v_id = v.vendor_id
                    v_details = f"Exact Tax ID match with Vendor Master: {v.vendor_id} ({v.name})"
                    best_vendor = v
                    break

                # Fuzzy normalized similarity
                norm_master_vendor = normalize_vendor_for_matching(v.name)
                sim = difflib.SequenceMatcher(None, norm_ext_vendor, norm_master_vendor).ratio()
                if sim > best_sim:
                    best_sim = sim
                    best_vendor = v

            if v_status != ReferenceMatchStatus.EXACT and best_sim >= 0.85 and best_vendor:
                v_status = ReferenceMatchStatus.PARTIAL
                matched_v_id = best_vendor.vendor_id
                v_details = (
                    f"Fuzzy normalized match ({best_sim:.2f}) with Vendor Master: "
                    f"{best_vendor.vendor_id} ({best_vendor.name})"
                )

            # Check for Tax ID conflicts if vendor matched
            if best_vendor and v_status in {
                ReferenceMatchStatus.EXACT,
                ReferenceMatchStatus.PARTIAL,
            }:
                if (
                    vendor_tax_id
                    and best_vendor.tax_id
                    and vendor_tax_id.strip() != best_vendor.tax_id.strip()
                ):
                    discrepancies.append(
                        Discrepancy(
                            discrepancy_id=f"DISC-REF-002-{doc_id}",
                            document_id=doc_id,
                            rule_id="REF_002",
                            rule_name="Vendor Master Tax ID Conflict",
                            category=RuleCategory.REFERENCE_MATCH,
                            severity=Severity.MEDIUM,
                            outcome=ValidationOutcome.WARNING,
                            affected_fields=["vendor_tax_id", "vendor_name"],
                            expected_value=best_vendor.tax_id,
                            actual_value=vendor_tax_id,
                            explanation=(
                                f"Extracted tax ID '{vendor_tax_id}' conflicts with registered "
                                f"tax ID '{best_vendor.tax_id}' for vendor '{best_vendor.name}'."
                            ),
                            evidence_references=["vendor_tax_id"]
                            if "vendor_tax_id" in record.evidence
                            else [],
                            review_recommendation="Verify corporate tax identifier with vendor accounting.",
                        )
                    )

            if v_status == ReferenceMatchStatus.NOT_FOUND and vendor_name:
                discrepancies.append(
                    Discrepancy(
                        discrepancy_id=f"DISC-REF-003-{doc_id}",
                        document_id=doc_id,
                        rule_id="REF_003",
                        rule_name="Unregistered Vendor Master Entity",
                        category=RuleCategory.REFERENCE_MATCH,
                        severity=Severity.INFO,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["vendor_name"],
                        expected_value="Registered master vendor",
                        actual_value=vendor_name,
                        explanation=f"Vendor '{vendor_name}' is not currently registered in the vendor master catalog.",
                        evidence_references=["vendor_name"]
                        if "vendor_name" in record.evidence
                        else [],
                        review_recommendation="Create new vendor master record if approved by procurement.",
                    )
                )

        # 2. Match against Purchase Orders
        po_status = ReferenceMatchStatus.NOT_PROVIDED
        po_details = "No purchase order reference verified"

        if po_number and self.po_records:
            matched_po = next((p for p in self.po_records if p.po_number == po_number), None)
            if matched_po:
                expected_po_tot = Decimal(matched_po.expected_total)
                if total is not None and abs(expected_po_tot - total) <= Decimal("0.02"):
                    po_status = ReferenceMatchStatus.EXACT
                    po_details = f"PO {po_number} reconciled cleanly: Expected {expected_po_tot}, Total {total}"
                else:
                    po_status = ReferenceMatchStatus.CONFLICT
                    po_details = (
                        f"PO {po_number} value conflict: Approved {expected_po_tot} {matched_po.currency}, "
                        f"Invoice Total {total} {currency}"
                    )
                    discrepancies.append(
                        Discrepancy(
                            discrepancy_id=f"DISC-REF-001-{doc_id}",
                            document_id=doc_id,
                            rule_id="REF_001",
                            rule_name="Purchase Order Value Reconciliation",
                            category=RuleCategory.REFERENCE_MATCH,
                            severity=Severity.HIGH,
                            outcome=ValidationOutcome.FAIL,
                            affected_fields=["total", "purchase_order_number"],
                            expected_value=expected_po_tot,
                            actual_value=total,
                            difference=total - expected_po_tot if total is not None else None,
                            explanation=po_details,
                            evidence_references=["total", "purchase_order_number"],
                            review_recommendation="Verify whether PO change order is required for invoice amount variance.",
                        )
                    )
            else:
                po_status = ReferenceMatchStatus.NOT_FOUND
                po_details = f"PO number '{po_number}' not found in purchase order database."

        match_res = ReferenceMatchResult(
            vendor_match_status=v_status,
            po_match_status=po_status,
            matched_vendor_id=matched_v_id,
            details=f"Vendor: {v_details} | PO: {po_details}",
        )

        return match_res, discrepancies


def get_default_vendor_master() -> list[VendorMasterRecord]:
    """Provide a standard synthetic master catalog of approved vendor entities."""
    return [
        VendorMasterRecord(
            vendor_id="VEND-001",
            name="Apex Cloud Systems Inc.",
            tax_id="US-EIN-94-3829102",
            address="100 Innovation Way, Suite 400, San Jose, CA 95110",
            default_currency="USD",
        ),
        VendorMasterRecord(
            vendor_id="VEND-002",
            name="Beacon Logistics GmbH",
            tax_id="DE-VAT-194820194",
            address="Industriestrasse 42, 60311 Frankfurt am Main, Germany",
            default_currency="EUR",
        ),
        VendorMasterRecord(
            vendor_id="VEND-003",
            name="Crestview Media Solutions Ltd.",
            tax_id="GB-VAT-982-1049-33",
            address="15 Soho Square, London W1D 3QL, United Kingdom",
            default_currency="GBP",
        ),
        VendorMasterRecord(
            vendor_id="VEND-004",
            name="Delta Office Furnishings Co.",
            tax_id="US-EIN-55-9102847",
            address="742 Evergreen Terrace, Springfield, OR 97477",
            default_currency="USD",
        ),
        VendorMasterRecord(
            vendor_id="VEND-005",
            name="Epsilon Software Labs",
            tax_id="US-EIN-12-3498172",
            address="88 Silicon Alley, 9th Floor, New York, NY 10010",
            default_currency="USD",
        ),
        VendorMasterRecord(
            vendor_id="VEND-006",
            name="Fjord Nordic Maritime Services",
            tax_id="NO-MVA-918273645",
            address="Havnegata 12, 0150 Oslo, Norway",
            default_currency="GBP",
        ),
    ]


def get_default_po_database() -> list[PurchaseOrderReference]:
    """Provide a sample synthetic purchase order reference catalog."""
    return [
        PurchaseOrderReference(
            po_number="PO-2024-001",
            vendor_name="Beacon Logistics GmbH",
            expected_total="589.05",
            currency="EUR",
        ),
        PurchaseOrderReference(
            po_number="PO-2024-002",
            vendor_name="Crestview Media Solutions Ltd.",
            expected_total="1500.00",
            currency="GBP",
        ),
    ]
