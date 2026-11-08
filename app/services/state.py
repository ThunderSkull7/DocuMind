"""Application state management and persistence adapter for DocuMind Streamlit UI.

Provides stable singleton services, shared repository models across page navigation,
session state synchronization, and optional JSON state persistence.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from documind.config import get_settings
from documind.extraction.field_extractor import StructuredInvoiceExtractor
from documind.extraction.service import ExtractionService
from documind.ingestion.models import IngestionMetadata, IngestionResult
from documind.ingestion.service import IngestionService
from documind.review.audit import AuditEvent, AuditTrail
from documind.review.models import ReviewRecord
from documind.review.service import ReviewService
from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.models import ValidationResult
from documind.validation.service import ValidationService

logger = logging.getLogger(__name__)

_GLOBAL_APP_STATE = None
_STATE_LOCK = threading.Lock()


def _atomic_write_json(file_path: Path, data: Any) -> None:
    """Atomically write JSON data using a temporary file and atomic replace."""
    tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    try:
        content = json.dumps(data, indent=2, default=str)
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, file_path)
    except Exception as exc:
        if tmp_path.is_file():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        logger.warning(f"Failed to atomically write {file_path}: {exc}")
        raise


class AppState:
    """Central state and coordination adapter for Streamlit application sessions."""

    def __init__(self, persistence_dir: Path | None = None) -> None:
        self.settings = get_settings()
        self.persistence_dir = persistence_dir or Path(self.settings.storage_dir) / "app_state"
        self.persistence_dir.mkdir(parents=True, exist_ok=True)

        self.audit_trail = AuditTrail()
        self.validation_service = ValidationService()
        self.review_service = ReviewService(
            audit_trail=self.audit_trail,
            validation_service=self.validation_service,
        )
        self.ingestion_service = IngestionService(settings=self.settings)
        self.extraction_service = ExtractionService(settings=self.settings)
        self.field_extractor = StructuredInvoiceExtractor()

        # In-memory repositories
        self.documents: dict[str, IngestionMetadata] = {}
        self.extractions: dict[str, InvoiceExtractionRecord] = {}
        self.validations: dict[str, ValidationResult] = {}
        self.document_paths: dict[str, Path] = {}

        self._lock = threading.Lock()
        self.load_from_disk()

    def process_document_bytes(
        self,
        content: bytes,
        filename: str,
        actor: str = "reviewer",
    ) -> tuple[bool, str, str | None]:
        """Ingest, extract, validate, and register a review record for raw PDF bytes.

        Returns:
            Tuple of (success: bool, message: str, document_id: str | None)
        """
        ingest_res: IngestionResult = self.ingestion_service.ingest(
            file_input=content,
            original_filename=filename,
        )

        if not ingest_res.success or not ingest_res.metadata:
            return False, f"Ingestion rejected: {ingest_res.error_message}", None

        meta = ingest_res.metadata
        doc_id = meta.document_id

        # Check if already processed (by hash or document_id)
        with self._lock:
            for prior_id, prior_meta in self.documents.items():
                if prior_meta.sha256_hash == meta.sha256_hash:
                    return (
                        True,
                        f"Document '{prior_id}' (identical payload hash) already processed and registered.",
                        prior_id,
                    )
            if doc_id in self.extractions:
                return True, f"Document '{doc_id}' already processed and registered.", doc_id

        # Run extraction
        raw_extract = self.extraction_service.extract_from_bytes(
            content=content,
            document_id=doc_id,
            source_file_hash=meta.sha256_hash,
        )

        # Run structured field extraction
        record = self.field_extractor.extract(raw_extract, file_name=filename)

        # Run Phase 5 validation
        val_res = self.validation_service.validate_record(record, source_hash=meta.sha256_hash)
        self.validation_service.duplicates.add_record(record, source_hash=meta.sha256_hash)

        # Create Phase 6 review record
        with self._lock:
            self.documents[doc_id] = meta
            self.extractions[doc_id] = record
            self.validations[doc_id] = val_res
            if meta.storage_path:
                self.document_paths[doc_id] = Path(self.settings.storage_dir) / meta.storage_path
            else:
                self.document_paths[doc_id] = Path("data/synthetic_documents") / filename

            # Create review record if not already active
            active_rev = self.review_service.get_active_review_for_document(doc_id)
            if not active_rev:
                self.review_service.create_review(
                    record=record,
                    validation_result=val_res,
                    actor=actor,
                )

        self.save_to_disk()
        return True, f"Document '{doc_id}' successfully ingested and validated.", doc_id

    def load_synthetic_corpus_sample(self, limit: int = 10, offset: int = 0) -> int:
        """Load a batch of synthetic invoices from the corpus into the application."""
        manifest_path = Path("data/manifest.json")
        if not manifest_path.is_file():
            return 0

        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest_data.get("documents", [])[offset : offset + limit]

        loaded_count = 0
        for entry in entries:
            doc_id = entry["document_id"]
            with self._lock:
                if doc_id in self.extractions:
                    continue

            pdf_path = Path("data/synthetic_documents") / entry["file_name"]
            if not pdf_path.is_file():
                continue

            content = pdf_path.read_bytes()
            success, _, _ = self.process_document_bytes(
                content=content,
                filename=entry["file_name"],
                actor="corpus_loader",
            )
            if success:
                loaded_count += 1

        return loaded_count

    def save_to_disk(self) -> None:
        """Persist reviews, audit events, extractions, validations and documents to disk."""
        try:
            with self._lock:
                all_reviews = [
                    r.model_dump(mode="json") for r in self.review_service.list_reviews()
                ]
                all_events = [e.model_dump(mode="json") for e in self.audit_trail.get_events()]
                all_extractions = {
                    k: v.model_dump(mode="json") for k, v in self.extractions.items()
                }
                all_validations = {
                    k: v.model_dump(mode="json") for k, v in self.validations.items()
                }
                all_docs = {k: v.model_dump(mode="json") for k, v in self.documents.items()}
                all_paths = {k: str(v) for k, v in self.document_paths.items()}

            _atomic_write_json(self.persistence_dir / "reviews.json", all_reviews)
            _atomic_write_json(self.persistence_dir / "audit.json", all_events)
            _atomic_write_json(self.persistence_dir / "extractions.json", all_extractions)
            _atomic_write_json(self.persistence_dir / "validations.json", all_validations)
            _atomic_write_json(self.persistence_dir / "documents.json", all_docs)
            _atomic_write_json(self.persistence_dir / "paths.json", all_paths)
        except Exception as exc:
            logger.warning(f"Error persisting app state to disk: {exc}")

    def _safe_load_json_file(self, file_path: Path) -> Any | None:
        """Load JSON from disk safely; preserve corrupted snapshots with a timestamp backup."""
        if not file_path.is_file():
            return None
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            corrupt_backup = file_path.with_name(
                f"{file_path.stem}.corrupted_{int(time.time())}{file_path.suffix}"
            )
            try:
                os.replace(file_path, corrupt_backup)
                logger.error(
                    f"Corrupted snapshot detected in {file_path}. Moved to {corrupt_backup}: {exc}"
                )
            except OSError as move_exc:
                logger.error(f"Failed to move corrupted file {file_path}: {move_exc}")
            return None

    def load_from_disk(self) -> None:
        """Load persisted reviews, audit events, extractions and documents from disk if available."""
        # 1. Audit events
        audit_data = self._safe_load_json_file(self.persistence_dir / "audit.json")
        if isinstance(audit_data, list):
            for e_dict in audit_data:
                try:
                    evt = AuditEvent.model_validate(e_dict)
                    with self.audit_trail._lock:
                        if not any(x.event_id == evt.event_id for x in self.audit_trail._events):
                            self.audit_trail._events.append(evt)
                except Exception as exc:
                    logger.warning(f"Skipping malformed audit event: {exc}")

        # 2. Review records
        reviews_data = self._safe_load_json_file(self.persistence_dir / "reviews.json")
        if isinstance(reviews_data, list):
            for r_dict in reviews_data:
                try:
                    rev = ReviewRecord.model_validate(r_dict)
                    with self.review_service._lock:
                        self.review_service._reviews[rev.review_id] = rev
                        self.review_service._document_reviews.setdefault(
                            rev.document_id, []
                        ).append(rev.review_id)
                except Exception as exc:
                    logger.warning(f"Skipping malformed review record: {exc}")

        # 3. Documents metadata
        docs_data = self._safe_load_json_file(self.persistence_dir / "documents.json")
        if isinstance(docs_data, dict):
            with self._lock:
                for doc_id, m_dict in docs_data.items():
                    try:
                        self.documents[doc_id] = IngestionMetadata.model_validate(m_dict)
                    except Exception as exc:
                        logger.warning(f"Skipping malformed ingestion metadata for {doc_id}: {exc}")

        # 4. Extractions
        extractions_data = self._safe_load_json_file(self.persistence_dir / "extractions.json")
        if isinstance(extractions_data, dict):
            with self._lock:
                for doc_id, ext_dict in extractions_data.items():
                    try:
                        self.extractions[doc_id] = InvoiceExtractionRecord.model_validate(ext_dict)
                    except Exception as exc:
                        logger.warning(f"Skipping malformed extraction record for {doc_id}: {exc}")

        # 5. Validations
        validations_data = self._safe_load_json_file(self.persistence_dir / "validations.json")
        if isinstance(validations_data, dict):
            with self._lock:
                for doc_id, val_dict in validations_data.items():
                    try:
                        val_res = ValidationResult.model_validate(val_dict)
                        self.validations[doc_id] = val_res
                    except Exception as exc:
                        logger.warning(f"Skipping malformed validation result for {doc_id}: {exc}")

        # 6. Paths
        paths_data = self._safe_load_json_file(self.persistence_dir / "paths.json")
        if isinstance(paths_data, dict):
            with self._lock:
                for doc_id, p_str in paths_data.items():
                    self.document_paths[doc_id] = Path(p_str)


def get_app_state() -> AppState:
    """Retrieve thread-safe global application state instance."""
    global _GLOBAL_APP_STATE
    with _STATE_LOCK:
        if _GLOBAL_APP_STATE is None:
            _GLOBAL_APP_STATE = AppState()
        return _GLOBAL_APP_STATE
