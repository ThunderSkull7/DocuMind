"""Integration tests verifying full corpus business rule validation across all 50 documents."""

import json
from pathlib import Path

import pytest

from documind.extraction.field_extractor import StructuredInvoiceExtractor
from documind.extraction.service import ExtractionService
from documind.validation.models import OverallValidationStatus
from documind.validation.service import ValidationService


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
def test_full_corpus_business_validation(
    extraction_service: ExtractionService,
    field_extractor: StructuredInvoiceExtractor,
    manifest_documents: list[dict],
) -> None:
    """Verify that all 50 documents are validated and deliberate injected edge cases are flagged."""
    val_service = ValidationService()

    results_by_doc: dict[str, OverallValidationStatus] = {}
    discrepancies_by_doc: dict[str, list] = {}

    for entry in manifest_documents:
        doc_id = entry["document_id"]
        pdf_path = Path("data/synthetic_documents") / entry["file_name"]

        raw_res = extraction_service.extract_from_bytes(
            pdf_path.read_bytes(),
            document_id=doc_id,
            source_file_hash=entry["sha256_hash"],
        )

        record = field_extractor.extract(raw_res, file_name=entry["file_name"])
        val_res = val_service.validate_record(record, source_hash=entry["sha256_hash"])
        val_service.duplicates.add_record(record)

        results_by_doc[doc_id] = val_res.overall_status
        discrepancies_by_doc[doc_id] = val_res.discrepancies

        # Ensure all discrepancies have valid rule IDs and non-empty explanations
        for d in val_res.discrepancies:
            assert d.rule_id
            assert d.explanation
            assert d.category

    # 1. Deliberately missing fields -> INVALID
    assert results_by_doc["DOC-SYN-007"] == OverallValidationStatus.INVALID
    assert any(d.rule_id == "BIZ_001" for d in discrepancies_by_doc["DOC-SYN-007"])

    assert results_by_doc["DOC-SYN-018"] == OverallValidationStatus.INVALID
    assert any(d.rule_id == "BIZ_001" for d in discrepancies_by_doc["DOC-SYN-018"])

    assert results_by_doc["DOC-SYN-035"] == OverallValidationStatus.INVALID
    assert any(d.rule_id == "BIZ_001" for d in discrepancies_by_doc["DOC-SYN-035"])

    # 2. Deliberate arithmetic mismatches -> NEEDS_REVIEW (ARITH_003)
    assert results_by_doc["DOC-SYN-015"] == OverallValidationStatus.NEEDS_REVIEW
    assert any(d.rule_id == "ARITH_003" for d in discrepancies_by_doc["DOC-SYN-015"])

    assert results_by_doc["DOC-SYN-041"] == OverallValidationStatus.NEEDS_REVIEW
    assert any(d.rule_id == "ARITH_003" for d in discrepancies_by_doc["DOC-SYN-041"])

    # 3. Deliberate duplicate identifier across vendors -> NEEDS_REVIEW (DUP_003)
    assert results_by_doc["DOC-SYN-045"] == OverallValidationStatus.NEEDS_REVIEW
    assert any(d.rule_id == "DUP_003" for d in discrepancies_by_doc["DOC-SYN-045"])

    # 4. Deliberate ambiguous date -> VALID_WITH_WARNINGS (BIZ_004)
    assert results_by_doc["DOC-SYN-023"] == OverallValidationStatus.VALID_WITH_WARNINGS
    assert any(d.rule_id == "BIZ_004" for d in discrepancies_by_doc["DOC-SYN-023"])

    # 5. Deliberate confusable glyphs -> VALID_WITH_WARNINGS (BIZ_008)
    assert results_by_doc["DOC-SYN-029"] == OverallValidationStatus.VALID_WITH_WARNINGS
    assert any(d.rule_id == "BIZ_008" for d in discrepancies_by_doc["DOC-SYN-029"])

    # 6. Overall distribution check
    invalid_docs = [k for k, v in results_by_doc.items() if v == OverallValidationStatus.INVALID]
    needs_review_docs = [
        k for k, v in results_by_doc.items() if v == OverallValidationStatus.NEEDS_REVIEW
    ]
    valid_with_warn_docs = [
        k for k, v in results_by_doc.items() if v == OverallValidationStatus.VALID_WITH_WARNINGS
    ]
    valid_docs = [k for k, v in results_by_doc.items() if v == OverallValidationStatus.VALID]

    assert len(invalid_docs) == 3
    assert len(needs_review_docs) == 3
    assert len(valid_with_warn_docs) == 2
    assert len(valid_docs) == 42
    assert (
        len(invalid_docs) + len(needs_review_docs) + len(valid_with_warn_docs) + len(valid_docs)
        == 50
    )
