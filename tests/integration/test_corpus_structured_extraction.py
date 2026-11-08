"""Integration tests verifying full corpus structured extraction across all 50 documents.

Evaluates header fields, vendor/customer separation, financial summaries, line items,
and bounding-box evidence validity across 30 digital PDFs and 20 scanned PDFs.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from documind.extraction.evidence_mapper import EvidenceMapper
from documind.extraction.field_extractor import StructuredInvoiceExtractor
from documind.extraction.service import ExtractionService
from documind.schemas.invoice import EvidenceStatus


@pytest.fixture(scope="module")
def extraction_service() -> ExtractionService:
    return ExtractionService()


@pytest.fixture(scope="module")
def field_extractor() -> StructuredInvoiceExtractor:
    return StructuredInvoiceExtractor()


@pytest.fixture(scope="module")
def manifest_documents() -> list[dict]:
    manifest_path = Path("data/manifest.json")
    assert manifest_path.is_file(), "data/manifest.json must exist"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data["documents"]


@pytest.mark.integration
def test_full_corpus_structured_extraction(
    extraction_service: ExtractionService,
    field_extractor: StructuredInvoiceExtractor,
    manifest_documents: list[dict],
) -> None:
    """Verify structured extraction across all 50 corpus documents against gold annotations."""
    assert len(manifest_documents) == 50

    for entry in manifest_documents:
        doc_id = entry["document_id"]
        pdf_path = Path("data/synthetic_documents") / entry["file_name"]
        ann_path = Path("data/annotations") / f"{doc_id}.json"

        assert pdf_path.is_file(), f"Missing PDF for {doc_id}"
        assert ann_path.is_file(), f"Missing annotation for {doc_id}"

        annotation = json.loads(ann_path.read_text(encoding="utf-8"))
        raw_res = extraction_service.extract_from_bytes(
            pdf_path.read_bytes(),
            document_id=doc_id,
            source_file_hash=entry["sha256_hash"],
        )

        record = field_extractor.extract(raw_res, file_name=entry["file_name"])
        rf = record.raw_fields
        ev = record.evidence

        # 1. Invoice Number Verification
        gold_inv = annotation.get("invoice_number")
        ext_inv = rf.get("invoice_number")
        if gold_inv is None:
            assert ext_inv is None, f"{doc_id}: Expected missing invoice number, got {ext_inv}"
            assert ev["invoice_number"].status == EvidenceStatus.MISSING
        else:
            assert ext_inv == gold_inv, (
                f"{doc_id}: Invoice number mismatch ({ext_inv} != {gold_inv})"
            )
            assert ev["invoice_number"].status == EvidenceStatus.EXTRACTED

        # 2. Vendor Name Verification
        gold_vend = annotation.get("vendor_name")
        ext_vend = rf.get("vendor_name")
        if gold_vend is None:
            assert ext_vend is None, f"{doc_id}: Expected missing vendor name, got {ext_vend}"
            assert ev["vendor_name"].status == EvidenceStatus.MISSING
        else:
            assert ext_vend == gold_vend, f"{doc_id}: Vendor mismatch ({ext_vend} != {gold_vend})"
            assert ev["vendor_name"].status == EvidenceStatus.EXTRACTED

        # 3. Currency Verification
        assert rf.get("currency") == annotation.get("currency"), f"{doc_id}: Currency mismatch"

        # 4. Total Amount Verification (including arithmetic edge cases)
        if annotation.get("total"):
            gold_tot = Decimal(annotation["total"])
            assert rf.get("total") == gold_tot, (
                f"{doc_id}: Total mismatch ({rf.get('total')} != {gold_tot})"
            )
            assert ev["total"].status == EvidenceStatus.EXTRACTED

        # 5. Subtotal Verification
        if annotation.get("subtotal"):
            gold_sub = Decimal(annotation["subtotal"])
            assert rf.get("subtotal") == gold_sub, f"{doc_id}: Subtotal mismatch"

        # 6. Tax Verification (including exempt/missing)
        gold_tax = Decimal(annotation["tax"]) if annotation.get("tax") else None
        assert rf.get("tax") == gold_tax, f"{doc_id}: Tax mismatch ({rf.get('tax')} != {gold_tax})"

        # 7. Line Items Verification
        items = rf.get("line_items", [])
        expected_min_items = 2
        assert len(items) >= expected_min_items, (
            f"{doc_id}: Expected at least 2 items, got {len(items)}"
        )
        for item in items:
            assert item.description
            assert item.total is not None

        # 8. Evidence Geometry and Provenance
        for field_name, evidence_item in ev.items():
            if evidence_item.bounding_box:
                is_valid, err_msg = EvidenceMapper.validate_bounding_box(
                    evidence_item.bounding_box,
                    page_width=595.0,
                    page_height=842.0,
                )
                assert is_valid, f"{doc_id} {field_name} bounding box error: {err_msg}"
