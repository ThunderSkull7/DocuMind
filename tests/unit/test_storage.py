"""Unit tests for secure document storage subsystem."""

import hashlib
from pathlib import Path

import pytest

from documind.config import Settings
from documind.exceptions import PathTraversalError, StorageError
from documind.ingestion.storage import StorageManager, sanitize_filename


@pytest.fixture
def storage_mgr(temp_dir: Path) -> StorageManager:
    """Provide a StorageManager using an isolated temporary directory."""
    settings = Settings(
        project_root=temp_dir,
        DOCUMIND_STORAGE_DIR="test_storage",
    )
    return StorageManager(settings)


@pytest.mark.unit
def test_filename_sanitization() -> None:
    """Verify filename sanitization removes directory traversals and dangerous patterns."""
    assert sanitize_filename("../../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("..\\..\\Windows\\System32\\cmd.pdf") == "cmd.pdf"
    assert sanitize_filename("invoice #123 (v1).pdf") == "invoice__123__v1_.pdf"
    assert sanitize_filename("safe_invoice.pdf") == "safe_invoice.pdf"
    assert sanitize_filename("") == "document.pdf"
    assert sanitize_filename("....pdf") == "document.pdf"


@pytest.mark.unit
def test_successful_storage(storage_mgr: StorageManager) -> None:
    """Verify storing content creates isolated document folder and returns expected tuple."""
    sample_bytes = b"%PDF-1.4 dummy content"
    doc_id, safe_name, file_hash, stored_path = storage_mgr.store(
        content=sample_bytes,
        original_filename="Client Invoice #1.pdf",
    )

    assert doc_id is not None
    assert safe_name == "Client_Invoice__1.pdf"
    assert file_hash == hashlib.sha256(sample_bytes).hexdigest()
    assert stored_path.is_file()
    assert stored_path.read_bytes() == sample_bytes
    assert storage_mgr.exists(doc_id)
    assert storage_mgr.retrieve(doc_id) == stored_path


@pytest.mark.unit
def test_path_traversal_detection(storage_mgr: StorageManager) -> None:
    """Verify PathTraversalError is raised if an invalid document ID is passed."""
    with pytest.raises(PathTraversalError):
        storage_mgr.get_document_dir("../../../traversal")

    with pytest.raises(PathTraversalError):
        storage_mgr.get_document_dir("doc/subfolder")


@pytest.mark.unit
def test_atomic_storage_cleanup_on_error(
    storage_mgr: StorageManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that if target rename fails, temporary files are cleanly removed."""
    sample_bytes = b"%PDF-1.4 content"

    def broken_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("Simulated disk replacement failure")

    monkeypatch.setattr(Path, "replace", broken_replace)

    with pytest.raises(StorageError):
        storage_mgr.store(
            content=sample_bytes,
            original_filename="test_fail.pdf",
            document_id="doc-fail-1",
        )

    # Confirm no orphan files left in document directory
    doc_dir = storage_mgr.get_document_dir("doc-fail-1")
    if doc_dir.exists():
        assert len(list(doc_dir.iterdir())) == 0


@pytest.mark.unit
def test_duplicate_uploads_isolated(storage_mgr: StorageManager) -> None:
    """Verify duplicate uploads receive distinct internal IDs and do not overwrite each other."""
    content = b"%PDF-1.4 identical content"
    id1, _, hash1, path1 = storage_mgr.store(content, "invoice.pdf")
    id2, _, hash2, path2 = storage_mgr.store(content, "invoice.pdf")

    assert id1 != id2
    assert hash1 == hash2
    assert path1 != path2
    assert path1.exists()
    assert path2.exists()
