"""Duplicate invoice detection engine utilizing cryptographic hashes and identity matching.

Identifies exact hash duplicates, identical vendor-identifier pairs, and potential
fuzzy duplicates (similar identifiers, matching amounts and dates) without deleting records.
"""

import difflib
from datetime import date
from decimal import Decimal

from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.models import (
    Discrepancy,
    DuplicateCheckResult,
    DuplicateMatchType,
    RuleCategory,
    Severity,
    ValidationOutcome,
)


def normalize_vendor_for_matching(name: str | None) -> str:
    """Normalize vendor name for duplicate screening."""
    if not name:
        return ""
    norm = name.lower()
    for term in [
        "inc.",
        "inc",
        "llc",
        "ltd.",
        "ltd",
        "gmbh",
        "corp.",
        "corp",
        "co.",
        "co",
        "b.v.",
        "bv",
    ]:
        norm = norm.replace(term, "")
    return "".join(c for c in norm if c.isalnum()).strip()


class DuplicateDetector:
    """Screening engine to detect duplicate invoice submissions across document repositories."""

    def __init__(self, historical_records: list[InvoiceExtractionRecord] | None = None) -> None:
        self.records: list[InvoiceExtractionRecord] = historical_records or []
        self.file_hashes: dict[str, str] = {}

    def add_record(self, record: InvoiceExtractionRecord, source_hash: str | None = None) -> None:
        """Register a processed invoice record into the screening history."""
        self.records.append(record)
        if source_hash:
            self.file_hashes[record.document_id] = source_hash

    def check_duplicate(
        self,
        record: InvoiceExtractionRecord,
        source_hash: str | None = None,
    ) -> tuple[DuplicateCheckResult, Discrepancy | None]:
        """Evaluate candidate invoice against registered history for duplicate signals."""
        doc_id = record.document_id

        # Signal 0: Exact Source File Hash
        if source_hash:
            for prior_doc_id, prior_hash in self.file_hashes.items():
                if prior_doc_id != doc_id and prior_hash == source_hash:
                    res = DuplicateCheckResult(
                        is_duplicate=True,
                        match_type=DuplicateMatchType.EXACT_HASH,
                        matching_document_ids=[prior_doc_id],
                        similarity_score=1.0,
                        explanation=(
                            f"Exact file payload SHA-256 duplicate detected matching existing document "
                            f"'{prior_doc_id}'."
                        ),
                        recommendation="Reject duplicate upload; document is identical to existing record.",
                    )
                    disc = Discrepancy(
                        discrepancy_id=f"DISC-DUP-000-{doc_id}-{prior_doc_id}",
                        document_id=doc_id,
                        rule_id="DUP_000",
                        rule_name="Exact File Hash Duplicate",
                        category=RuleCategory.DUPLICATE,
                        severity=Severity.HIGH,
                        outcome=ValidationOutcome.FAIL,
                        affected_fields=["file_hash"],
                        expected_value="Unique document payload hash",
                        actual_value=source_hash,
                        explanation=res.explanation,
                        evidence_references=[],
                        review_recommendation=res.recommendation,
                    )
                    return res, disc

        inv_num = record.raw_fields.get("invoice_number")
        vendor = record.raw_fields.get("vendor_name")
        total: Decimal | None = record.raw_fields.get("total")
        inv_date = record.raw_fields.get("invoice_date")

        norm_vendor = normalize_vendor_for_matching(vendor)

        for prior in self.records:
            if prior.document_id == doc_id:
                continue  # Skip comparison against self

            prior_rf = prior.raw_fields
            prior_inv = prior_rf.get("invoice_number")
            prior_vend = prior_rf.get("vendor_name")
            prior_total: Decimal | None = prior_rf.get("total")
            prior_date = prior_rf.get("invoice_date")
            prior_norm_vend = normalize_vendor_for_matching(prior_vend)

            # Signal 1: Identical Invoice Number
            if inv_num and prior_inv and inv_num == prior_inv:
                if norm_vendor and prior_norm_vend and norm_vendor == prior_norm_vend:
                    # Same vendor and same invoice number -> Exact Identity Match
                    res = DuplicateCheckResult(
                        is_duplicate=True,
                        match_type=DuplicateMatchType.EXACT_IDENTITY,
                        matching_document_ids=[prior.document_id],
                        similarity_score=1.0,
                        explanation=(
                            f"Exact duplicate invoice identifier '{inv_num}' detected for vendor "
                            f"'{vendor}' matching existing document '{prior.document_id}'."
                        ),
                        recommendation="Flag document as suspected duplicate submission; hold payment.",
                    )
                    disc = Discrepancy(
                        discrepancy_id=f"DISC-DUP-001-{doc_id}-{prior.document_id}",
                        document_id=doc_id,
                        rule_id="DUP_001",
                        rule_name="Duplicate Invoice Identifier for Vendor",
                        category=RuleCategory.DUPLICATE,
                        severity=Severity.HIGH,
                        outcome=ValidationOutcome.FAIL,
                        affected_fields=["invoice_number", "vendor_name"],
                        expected_value="Unique invoice identifier per vendor",
                        actual_value=inv_num,
                        explanation=res.explanation,
                        evidence_references=["invoice_number", "vendor_name"],
                        review_recommendation=res.recommendation,
                    )
                    return res, disc
                else:
                    # Different vendors sharing the exact same invoice number
                    res = DuplicateCheckResult(
                        is_duplicate=True,
                        match_type=DuplicateMatchType.POTENTIAL_MATCH,
                        matching_document_ids=[prior.document_id],
                        similarity_score=0.90,
                        explanation=(
                            f"Shared duplicate invoice number identifier '{inv_num}' detected across "
                            f"different vendors: '{vendor}' and '{prior_vend}' ({prior.document_id})."
                        ),
                        recommendation="Verify whether duplicate identifier is an accidental reuse across vendors.",
                    )
                    disc = Discrepancy(
                        discrepancy_id=f"DISC-DUP-003-{doc_id}-{prior.document_id}",
                        document_id=doc_id,
                        rule_id="DUP_003",
                        rule_name="Duplicate Invoice Identifier Across Different Vendors",
                        category=RuleCategory.DUPLICATE,
                        severity=Severity.MEDIUM,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["invoice_number", "vendor_name"],
                        expected_value="Unique invoice numbering across supplier pool",
                        actual_value=inv_num,
                        explanation=res.explanation,
                        evidence_references=["invoice_number", "vendor_name"],
                        review_recommendation=res.recommendation,
                    )
                    return res, disc

            # Signal 2: Potential Duplicate (Same vendor, same total amount with proximate dates)
            if (
                norm_vendor
                and prior_norm_vend
                and norm_vendor == prior_norm_vend
                and total is not None
                and prior_total is not None
                and total == prior_total
            ):
                dates_close = False
                if (
                    inv_date
                    and prior_date
                    and isinstance(inv_date, date)
                    and isinstance(prior_date, date)
                ):
                    # Flag if within 14 days (routine monthly billing is >= 28 days apart)
                    dates_close = abs((inv_date - prior_date).days) <= 14

                # Check identifier string similarity (e.g. OCR misread like 0 vs O)
                id_sim = (
                    difflib.SequenceMatcher(None, inv_num or "", prior_inv or "").ratio()
                    if inv_num and prior_inv
                    else 0.0
                )

                if dates_close and id_sim >= 0.80:
                    res = DuplicateCheckResult(
                        is_duplicate=True,
                        match_type=DuplicateMatchType.POTENTIAL_MATCH,
                        matching_document_ids=[prior.document_id],
                        similarity_score=round(id_sim, 2),
                        explanation=(
                            f"Potential duplicate invoice for vendor '{vendor}' with identical total amount "
                            f"{total} and proximate dates/identifiers matching document '{prior.document_id}'."
                        ),
                        recommendation="Review both invoices side-by-side to ensure billing is not duplicated.",
                    )
                    disc = Discrepancy(
                        discrepancy_id=f"DISC-DUP-002-{doc_id}-{prior.document_id}",
                        document_id=doc_id,
                        rule_id="DUP_002",
                        rule_name="Potential Duplicate Invoice Submission",
                        category=RuleCategory.DUPLICATE,
                        severity=Severity.MEDIUM,
                        outcome=ValidationOutcome.WARNING,
                        affected_fields=["total", "vendor_name", "invoice_date"],
                        expected_value=f"Distinct billing event from {prior.document_id}",
                        actual_value=f"Total: {total}",
                        explanation=res.explanation,
                        evidence_references=["total", "vendor_name"],
                        review_recommendation=res.recommendation,
                    )
                    return res, disc

        return (
            DuplicateCheckResult(
                is_duplicate=False,
                match_type=DuplicateMatchType.NONE,
                matching_document_ids=[],
                similarity_score=0.0,
                explanation="No duplicate invoice detected in repository history.",
                recommendation="Proceed with standard processing.",
            ),
            None,
        )
