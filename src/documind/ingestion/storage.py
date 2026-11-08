"""Secure document storage manager for DocuMind.

Handles isolated, atomic document writes, path-traversal prevention,
SHA-256 hash calculation, and safe retrieval.
"""

import hashlib
import os
import re
import uuid
from pathlib import Path

from documind.config import Settings, get_settings
from documind.exceptions import PathTraversalError, StorageError
from documind.logging import get_logger

logger = get_logger("ingestion.storage")


def sanitize_filename(filename: str) -> str:
    """Sanitize client-provided filename to prevent directory traversal or filesystem exploits.

    Strips directory separators, relative path markers ('..'), control chars,
    and replaces risky symbols.
    """
    if not filename:
        return "document.pdf"

    # Extract basename only
    base = os.path.basename(filename.replace("\\", "/"))

    # If the stem is only dots or empty, fallback immediately
    stem = Path(base).stem.strip(". ")
    if not stem:
        return "document.pdf"

    # Remove any traversal patterns
    base = re.sub(r"\.\.+", "", base)

    # Allow alphanumeric, underscores, hyphens, and periods
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base)

    # Trim leading/trailing periods or whitespace
    sanitized = sanitized.strip(". ")

    if not sanitized or sanitized.lower() == "pdf":
        return "document.pdf"

    if not sanitized.lower().endswith(".pdf"):
        sanitized = f"{sanitized}.pdf"

    return sanitized


class StorageManager:
    """Manages document storage operations ensuring atomicity and isolation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage_root: Path = self.settings.storage_dir
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def calculate_sha256(self, content: bytes) -> str:
        """Compute the SHA-256 hexadecimal digest of file content."""
        return hashlib.sha256(content).hexdigest()

    def generate_document_id(self) -> str:
        """Generate a random UUIDv4 document identifier."""
        return str(uuid.uuid4())

    def get_document_dir(self, document_id: str) -> Path:
        """Get the isolated directory for a given document ID."""
        # Validate that document_id is safe and contains no traversal sequences
        if not re.match(r"^[a-zA-Z0-9_\-]+$", document_id):
            raise PathTraversalError(f"Invalid document identifier format: {document_id}")
        doc_dir = self.storage_root / document_id
        # Confirm resolved path remains within storage root
        if not doc_dir.resolve().is_relative_to(self.storage_root.resolve()):
            raise PathTraversalError(
                f"Path traversal detected: {doc_dir} is outside {self.storage_root}"
            )
        return doc_dir

    def store(
        self,
        content: bytes,
        original_filename: str,
        document_id: str | None = None,
    ) -> tuple[str, str, str, Path]:
        """Atomically store file content in an isolated document folder.

        Args:
            content: Raw binary document content.
            original_filename: Filename supplied by client.
            document_id: Optional predetermined ID; generated if None.

        Returns:
            Tuple of (document_id, sanitized_filename, sha256_hash, stored_path).

        Raises:
            StorageError: If atomic write or directory creation fails.
        """
        doc_id = document_id or self.generate_document_id()
        safe_name = sanitize_filename(original_filename)
        sha256_hash = self.calculate_sha256(content)

        doc_dir = self.get_document_dir(doc_id)
        doc_dir.mkdir(parents=True, exist_ok=True)

        target_path = doc_dir / safe_name
        temp_path = doc_dir / f"{safe_name}.{uuid.uuid4().hex[:8]}.tmp"

        try:
            # Atomic write practice: write to temp file then rename
            with open(temp_path, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace on target
            temp_path.replace(target_path)
            logger.info(f"Stored document id={doc_id} size={len(content)} bytes at {target_path}")

        except Exception as exc:
            # Clean up temporary file on failure
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            msg = f"Failed to store document {doc_id}: {exc}"
            logger.error(msg)
            raise StorageError(msg) from exc

        return doc_id, safe_name, sha256_hash, target_path

    def retrieve(self, document_id: str) -> Path | None:
        """Locate stored document file for a given document ID."""
        try:
            doc_dir = self.get_document_dir(document_id)
            if not doc_dir.exists():
                return None
            for item in doc_dir.iterdir():
                if (
                    item.is_file()
                    and item.suffix.lower() == ".pdf"
                    and not item.name.endswith(".tmp")
                ):
                    return item
        except PathTraversalError:
            return None
        return None

    def exists(self, document_id: str) -> bool:
        """Check whether a document exists in storage."""
        return self.retrieve(document_id) is not None
