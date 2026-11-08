"""Unit tests verifying AppState management, document processing, and local persistence."""

from pathlib import Path

from app.services.state import AppState

from documind.review.models import ReviewStatus
from documind.validation.models import OverallValidationStatus


def test_app_state_empty_initialization(tmp_path: Path) -> None:
    state = AppState(persistence_dir=tmp_path)
    assert len(state.documents) == 0
    assert len(state.extractions) == 0
    assert len(state.validations) == 0
    assert len(state.review_service.list_reviews()) == 0


def test_app_state_process_synthetic_invoice(tmp_path: Path) -> None:
    state = AppState(persistence_dir=tmp_path)
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    assert pdf_path.is_file(), "syn_invoice_001_digital.pdf must exist"

    content = pdf_path.read_bytes()
    success, msg, doc_id = state.process_document_bytes(
        content=content,
        filename="syn_invoice_001_digital.pdf",
        actor="test_runner",
    )

    assert success is True
    assert doc_id is not None
    assert doc_id in state.extractions
    assert doc_id in state.validations
    assert state.validations[doc_id].overall_status == OverallValidationStatus.VALID

    # Check review record created in PENDING
    rev = state.review_service.get_active_review_for_document(doc_id)
    assert rev is not None
    assert rev.status == ReviewStatus.PENDING

    # Idempotent re-processing
    success2, msg2, doc_id2 = state.process_document_bytes(
        content=content,
        filename="syn_invoice_001_digital.pdf",
    )
    assert success2 is True
    assert doc_id2 == doc_id
    assert "already processed" in msg2


def test_app_state_persistence_save_and_reload(tmp_path: Path) -> None:
    state = AppState(persistence_dir=tmp_path)
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    state.process_document_bytes(pdf_path.read_bytes(), "syn_invoice_001_digital.pdf")

    # Start review and approve
    reviews = state.review_service.list_reviews()
    r = reviews[0]
    state.review_service.start_review(r.review_id, reviewer="alice")
    state.review_service.approve_document(r.review_id, reviewer="alice", reason_code="VERIFIED")
    state.save_to_disk()

    # Re-initialize new AppState with same directory
    reloaded_state = AppState(persistence_dir=tmp_path)
    reloaded_revs = reloaded_state.review_service.list_reviews()
    assert len(reloaded_revs) == 1
    assert reloaded_revs[0].status == ReviewStatus.APPROVED
    assert len(reloaded_state.audit_trail.get_events()) >= 3
    assert len(reloaded_state.extractions) == 1
    assert len(reloaded_state.validations) == 1
    assert len(reloaded_state.documents) == 1


def test_app_state_corrupted_json_snapshot_recovery(tmp_path: Path) -> None:
    """Verify that malformed JSON snapshot files are backed up to .corrupted and do not crash load."""
    corrupted_file = tmp_path / "reviews.json"
    corrupted_file.write_text("{this is not valid json! truncated...", encoding="utf-8")

    # AppState should safely handle the corrupted file
    state = AppState(persistence_dir=tmp_path)
    assert len(state.review_service.list_reviews()) == 0

    # The corrupted file should have been renamed to .corrupted_*
    corrupted_backups = list(tmp_path.glob("reviews.corrupted_*"))
    assert len(corrupted_backups) == 1
    assert "truncated" in corrupted_backups[0].read_text(encoding="utf-8")


def test_app_state_atomic_write_behavior(tmp_path: Path) -> None:
    """Verify that save_to_disk writes files atomically without leaving dangling .tmp files."""
    state = AppState(persistence_dir=tmp_path)
    pdf_path = Path("data/synthetic_documents/syn_invoice_001_digital.pdf")
    state.process_document_bytes(pdf_path.read_bytes(), "syn_invoice_001_digital.pdf")
    state.save_to_disk()

    # Ensure all target json files exist and no .tmp files remain
    expected_files = [
        "reviews.json",
        "audit.json",
        "extractions.json",
        "validations.json",
        "documents.json",
        "paths.json",
    ]
    for fname in expected_files:
        assert (tmp_path / fname).is_file(), f"{fname} must exist after save_to_disk"

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0, "No dangling .tmp files should exist after atomic writes"
