"""Application state management and persistence adapter for DocuMind Streamlit UI.

Provides stable singleton services, shared repository models across page navigation,
session state synchronization, and optional JSON state persistence.
"""

import json
import threading
from pathlib import Path

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

_GLOBAL_APP_STATE = None
_STATE_LOCK = threading.Lock()


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
        """Persist reviews and audit events locally to preserve state across restarts."""
        try:
            reviews_path = self.persistence_dir / "reviews.json"
            audit_path = self.persistence_dir / "audit.json"

            all_reviews = [r.model_dump(mode="json") for r in self.review_service.list_reviews()]
            all_events = [e.model_dump(mode="json") for e in self.audit_trail.get_events()]

            reviews_path.write_text(
                json.dumps(all_reviews, indent=2, default=str), encoding="utf-8"
            )
            audit_path.write_text(json.dumps(all_events, indent=2, default=str), encoding="utf-8")
        except Exception:  # Non-fatal persistence logging
            pass

    def load_from_disk(self) -> None:
        """Load persisted reviews and audit events from disk if available."""
        try:
            reviews_path = self.persistence_dir / "reviews.json"
            audit_path = self.persistence_dir / "audit.json"

            if audit_path.is_file():
                raw_events = json.loads(audit_path.read_text(encoding="utf-8"))
                for e_dict in raw_events:
                    evt = AuditEvent.model_validate(e_dict)
                    with self.audit_trail._lock:
                        if not any(x.event_id == evt.event_id for x in self.audit_trail._events):
                            self.audit_trail._events.append(evt)

            if reviews_path.is_file():
                raw_reviews = json.loads(reviews_path.read_text(encoding="utf-8"))
                for r_dict in raw_reviews:
                    rev = ReviewRecord.model_validate(r_dict)
                    with self.review_service._lock:
                        self.review_service._reviews[rev.review_id] = rev
                        self.review_service._document_reviews.setdefault(
                            rev.document_id, []
                        ).append(rev.review_id)
        except Exception:  # Non-fatal recovery fallback
            pass


def get_app_state() -> AppState:
    """Retrieve thread-safe global application state instance."""
    global _GLOBAL_APP_STATE
    with _STATE_LOCK:
        if _GLOBAL_APP_STATE is None:
            _GLOBAL_APP_STATE = AppState()
        return _GLOBAL_APP_STATE
