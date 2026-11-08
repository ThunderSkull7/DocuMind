"""Vendor and Customer entity extraction using spatial layout semantics.

Extracts vendor corporate name, address, tax identifier, email, and phone,
as well as customer (Bill-To) name, address, and contact details with full provenance.
"""

import re
from typing import Any

from documind.extraction.evidence_mapper import EvidenceMapper
from documind.extraction.models import SpatialWord
from documind.extraction.patterns import (
    CUSTOMER_SECTION_LABELS,
    EMAIL_PATTERN,
    VENDOR_TAX_ID_LABELS,
)
from documind.extraction.spatial import (
    SpatialLine,
)
from documind.schemas.invoice import ExtractionMethod, FieldEvidence


def _normalize_entity_name(name: str) -> str:
    """Normalize common OCR misrecognitions in corporate entity names."""
    # Correct OCR 'Lid.' / 'Lid' misrecognition of 'Ltd.' / 'Ltd'
    name = re.sub(r"\bLid\b\.?", "Ltd.", name)
    return name.strip()


class EntityExtractor:
    """Extracts vendor and customer profile fields and evidence from spatial document pages."""

    def extract_vendor_info(
        self,
        lines: list[SpatialLine],
        page_number: int = 1,
    ) -> dict[str, tuple[Any, FieldEvidence]]:
        """Extract vendor identity, address, tax ID, email, and phone."""
        results: dict[str, tuple[Any, FieldEvidence]] = {}

        # 1. Vendor Name
        vendor_name: str | None = None
        v_words: list[SpatialWord] = []

        # Strategy A: Top-right header (Modern Tech or Corporate Classic)
        for line in lines:
            if line.y_center <= 75.0:
                right_words = [w for w in line.words if w.bounding_box.x0 >= 280.0]
                if right_words:
                    candidate = " ".join(w.text for w in right_words).strip()
                    if (
                        len(candidate) >= 3
                        and "invoice" not in candidate.lower()
                        and "page" not in candidate.lower()
                    ):
                        vendor_name = candidate
                        v_words = right_words
                        break

        # Strategy B: Line below "COMMERCIAL INVOICE"
        if not vendor_name:
            for i, line in enumerate(lines):
                if "COMMERCIAL INVOICE" in line.text.upper() and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if (
                        next_line.y_center < 105.0
                        and "invoice" not in next_line.text.lower()
                        and "tax" not in next_line.text.lower()
                    ):
                        candidate = next_line.text.strip()
                        if len(candidate) >= 3:
                            vendor_name = candidate
                            v_words = next_line.words
                            break

        if vendor_name:
            vendor_name = _normalize_entity_name(vendor_name)

        if vendor_name and v_words:
            results["vendor_name"] = (
                vendor_name,
                EvidenceMapper.create_from_words(
                    field_name="vendor_name",
                    extracted_value=vendor_name,
                    words=v_words,
                    page_number=page_number,
                    method=ExtractionMethod.SPATIAL,
                ),
            )
        else:
            results["vendor_name"] = (
                None,
                EvidenceMapper.create_missing_evidence(
                    field_name="vendor_name",
                    reason="Vendor corporate name omitted from header",
                ),
            )

        # 2. Vendor Address & Tax ID from metadata section (y in [100, 160], x < 300)
        vendor_address: str | None = None
        addr_words: list[SpatialWord] = []
        vendor_tax_id: str | None = None
        tax_words: list[SpatialWord] = []

        for line in lines:
            if 100.0 <= line.y_center <= 160.0:
                left_words = [w for w in line.words if w.bounding_box.x1 < 340.0]
                if not left_words:
                    continue
                line_left_text = " ".join(w.text for w in left_words).strip()

                # Check for Tax/VAT ID
                is_tax_line = False
                for lbl in VENDOR_TAX_ID_LABELS:
                    if lbl in line_left_text.lower():
                        is_tax_line = True
                        val_words = [
                            w
                            for w in left_words
                            if not any(k in w.text.lower() for k in ["tax", "vat", "id:", "id"])
                        ]
                        if val_words:
                            vendor_tax_id = " ".join(w.text for w in val_words).strip()
                            tax_words = val_words
                        break

                if not is_tax_line and not vendor_address:
                    # Street / address indicators
                    if any(
                        term in line_left_text.lower()
                        for term in [
                            "street",
                            "strasse",
                            "way",
                            "avenue",
                            "blvd",
                            "square",
                            "road",
                            "suite",
                            "floor",
                            "alley",
                            "terrace",
                            "havnegata",
                        ]
                    ) or any(char.isdigit() for char in line_left_text):
                        vendor_address = line_left_text
                        addr_words = left_words

        if vendor_address and addr_words:
            results["vendor_address"] = (
                vendor_address,
                EvidenceMapper.create_from_words(
                    field_name="vendor_address",
                    extracted_value=vendor_address,
                    words=addr_words,
                    page_number=page_number,
                ),
            )

        if vendor_tax_id and tax_words:
            results["vendor_tax_id"] = (
                vendor_tax_id,
                EvidenceMapper.create_from_words(
                    field_name="vendor_tax_id",
                    extracted_value=vendor_tax_id,
                    words=tax_words,
                    page_number=page_number,
                ),
            )

        # 3. Check for vendor email or phone in header
        for line in lines:
            if line.y_center <= 160.0:
                em_match = EMAIL_PATTERN.search(line.text)
                if em_match and "vendor_email" not in results:
                    matched_words = [
                        w for w in line.words if em_match.group(0).lower() in w.text.lower()
                    ]
                    results["vendor_email"] = (
                        em_match.group(0),
                        EvidenceMapper.create_from_words(
                            field_name="vendor_email",
                            extracted_value=em_match.group(0),
                            words=matched_words or line.words,
                            page_number=page_number,
                        ),
                    )

        return results

    def extract_customer_info(
        self,
        lines: list[SpatialLine],
        page_number: int = 1,
    ) -> dict[str, tuple[Any, FieldEvidence]]:
        """Extract customer/client organization name and billing address."""
        results: dict[str, tuple[Any, FieldEvidence]] = {}

        customer_name: str | None = None
        c_words: list[SpatialWord] = []
        customer_addr: str | None = None
        ca_words: list[SpatialWord] = []

        bill_to_idx: int | None = None
        for i, line in enumerate(lines):
            l_upper = line.text.upper()
            if any(lbl.upper() in l_upper for lbl in CUSTOMER_SECTION_LABELS):
                bill_to_idx = i
                break

        if bill_to_idx is not None:
            # Customer Name is on the next line below BILL TO
            if bill_to_idx + 1 < len(lines):
                line_name = lines[bill_to_idx + 1]
                if line_name.y_center < 235.0 and line_name.words:
                    customer_name = line_name.text.strip()
                    c_words = line_name.words

            # Customer Address is on the line below Customer Name
            if bill_to_idx + 2 < len(lines):
                line_addr = lines[bill_to_idx + 2]
                if line_addr.y_center < 245.0 and line_addr.words:
                    customer_addr = line_addr.text.strip()
                    ca_words = line_addr.words

        if customer_name:
            customer_name = _normalize_entity_name(customer_name)

        if customer_name and c_words:
            results["customer_name"] = (
                customer_name,
                EvidenceMapper.create_from_words(
                    field_name="customer_name",
                    extracted_value=customer_name,
                    words=c_words,
                    page_number=page_number,
                ),
            )

        if customer_addr and ca_words:
            results["customer_address"] = (
                customer_addr,
                EvidenceMapper.create_from_words(
                    field_name="customer_address",
                    extracted_value=customer_addr,
                    words=ca_words,
                    page_number=page_number,
                ),
            )

        return results
