"""Unit tests for synthetic dataset generation, annotations, and manifest verification."""

import hashlib
from pathlib import Path

import pymupdf
import pytest

from documind.dataset.generator import SyntheticInvoiceGenerator
from documind.dataset.models import (
    DatasetManifest,
    DocumentType,
    IssueType,
    SyntheticInvoiceAnnotation,
)


@pytest.mark.unit
def test_dataset_corpus_counts() -> None:
    """Verify that the generated corpus has exactly 50 documents (30 digital, 20 scanned)."""
    manifest_path = Path("data/manifest.json")
    assert manifest_path.exists(), "Manifest file data/manifest.json must exist."

    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert manifest.total_documents == 50
    assert manifest.digital_count == 30
    assert manifest.scanned_count == 20
    assert len(manifest.documents) == 50


@pytest.mark.unit
def test_annotation_file_consistency() -> None:
    """Verify every document has an annotation and every annotation points to a document."""
    manifest = DatasetManifest.model_validate_json(
        Path("data/manifest.json").read_text(encoding="utf-8")
    )
    annotations_dir = Path("data/annotations")
    docs_dir = Path("data/synthetic_documents")

    assert len(list(annotations_dir.glob("*.json"))) == 50
    assert len(list(docs_dir.glob("*.pdf"))) == 50

    for entry in manifest.documents:
        pdf_file = docs_dir / entry.file_name
        ann_file = annotations_dir / f"{entry.document_id}.json"

        assert pdf_file.is_file(), f"Document file missing: {pdf_file}"
        assert ann_file.is_file(), f"Annotation file missing: {ann_file}"

        # Verify SHA-256 match
        file_bytes = pdf_file.read_bytes()
        computed_hash = hashlib.sha256(file_bytes).hexdigest()
        assert computed_hash == entry.sha256_hash, f"Hash mismatch for {entry.file_name}"

        # Validate annotation schema
        ann = SyntheticInvoiceAnnotation.model_validate_json(ann_file.read_text(encoding="utf-8"))
        assert ann.document_id == entry.document_id
        assert ann.file_name == entry.file_name
        assert ann.document_type == entry.document_type


@pytest.mark.unit
def test_digital_vs_scanned_text_layer() -> None:
    """Verify digital PDFs contain native text while scanned PDFs have zero extractable text."""
    docs_dir = Path("data/synthetic_documents")
    manifest = DatasetManifest.model_validate_json(
        Path("data/manifest.json").read_text(encoding="utf-8")
    )

    for entry in manifest.documents:
        pdf_path = docs_dir / entry.file_name
        doc = pymupdf.open(str(pdf_path))
        first_page_text = doc[0].get_text().strip()

        if entry.document_type == DocumentType.DIGITAL:
            assert len(first_page_text) > 100, (
                f"Digital document {entry.file_name} lacks extractable text."
            )
        else:
            assert len(first_page_text) == 0, (
                f"Scanned document {entry.file_name} contains unexpected text layer."
            )
        doc.close()


@pytest.mark.unit
def test_deliberate_edge_cases_represented() -> None:
    """Verify deliberate edge cases are recorded in annotations."""
    annotations_dir = Path("data/annotations")
    issue_types_found: set[IssueType] = set()

    for ann_file in annotations_dir.glob("*.json"):
        ann = SyntheticInvoiceAnnotation.model_validate_json(ann_file.read_text(encoding="utf-8"))
        for issue in ann.deliberately_introduced_issues:
            issue_types_found.add(issue.issue_type)

    assert IssueType.MISSING_FIELD in issue_types_found
    assert IssueType.ARITHMETIC_MISMATCH in issue_types_found
    assert IssueType.AMBIGUOUS_DATE in issue_types_found
    assert IssueType.INCONSISTENT_DATES in issue_types_found
    assert IssueType.UNUSUAL_NUMBER_FORMAT in issue_types_found
    assert IssueType.SIMILAR_LOOKING_CHARS in issue_types_found
    assert IssueType.DUPLICATE_IDENTIFIER in issue_types_found
    assert IssueType.SCAN_SKEW in issue_types_found
    assert IssueType.SCAN_DEGRADATION in issue_types_found


@pytest.mark.unit
def test_deterministic_reproducibility(temp_dir: Path) -> None:
    """Verify generator yields identical document bytes when run with the same seed."""
    out_dir_1 = temp_dir / "run1"
    ann_dir_1 = temp_dir / "ann1"
    man_path_1 = temp_dir / "man1.json"

    out_dir_2 = temp_dir / "run2"
    ann_dir_2 = temp_dir / "ann2"
    man_path_2 = temp_dir / "man2.json"

    gen1 = SyntheticInvoiceGenerator(
        seed=100, output_dir=out_dir_1, annotations_dir=ann_dir_1, manifest_path=man_path_1
    )
    # Generate 2 docs for fast reproducibility test
    e1 = gen1._generate_invoice(1, "DOC-TEST-001", DocumentType.DIGITAL)

    gen2 = SyntheticInvoiceGenerator(
        seed=100, output_dir=out_dir_2, annotations_dir=ann_dir_2, manifest_path=man_path_2
    )
    e2 = gen2._generate_invoice(1, "DOC-TEST-001", DocumentType.DIGITAL)

    assert e1.sha256_hash == e2.sha256_hash
    bytes1 = (out_dir_1 / e1.file_name).read_bytes()
    bytes2 = (out_dir_2 / e2.file_name).read_bytes()
    assert bytes1 == bytes2
