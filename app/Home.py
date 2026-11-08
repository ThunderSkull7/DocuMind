"""DocuMind Streamlit Application - Entry Point.

Phase 2 foundation providing system diagnostics, synthetic corpus stats,
and isolated document ingestion verification.
"""

import sys

import streamlit as st

from documind import __version__
from documind.config import get_settings
from documind.dataset.models import DatasetManifest
from documind.ingestion.service import IngestionService


def main() -> None:
    st.set_page_config(
        page_title="DocuMind - Document Extraction & Verification",
        page_icon="📄",
        layout="wide",
    )

    settings = get_settings()

    st.title("📄 DocuMind")
    st.subheader("Intelligent Document Extraction & Verification System")

    st.info(
        f"**Phase 2 Active** — Synthetic Corpus & Secure Ingestion | Version {__version__} | Environment: `{settings.env}`"
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📥 Document Ingestion Demonstration")
        st.caption(
            "Upload an invoice PDF to test file signature checks, parser compatibility, "
            "atomic storage, and SHA-256 metadata generation."
        )

        uploaded_file = st.file_uploader(
            "Select invoice PDF",
            type=["pdf"],
            help=f"Enforces maximum size of {settings.max_upload_size_mb} MB and PDF magic bytes inspection.",
        )

        if uploaded_file is not None:
            service = IngestionService()
            result = service.ingest(
                file_input=uploaded_file,
                original_filename=uploaded_file.name,
            )

            if result.success:
                st.success(
                    f"✅ Document successfully validated and safely stored! Internal ID: `{result.metadata.document_id}`"
                )
                st.json(
                    {
                        "document_id": result.metadata.document_id,
                        "original_filename": result.metadata.original_filename,
                        "sanitized_filename": result.metadata.sanitized_filename,
                        "sha256_hash": result.metadata.sha256_hash,
                        "page_count": result.metadata.page_count,
                        "file_size_bytes": result.metadata.file_size_bytes,
                        "storage_path": result.metadata.storage_path,
                        "status": result.metadata.status.value,
                    }
                )
                st.info("ℹ️ Structured extraction and OCR fallback are scheduled for Phase 3.")
            else:
                st.error(f"❌ Ingestion rejected: {result.error_message}")
                st.write("**Validation Details:**", result.metadata.validation.model_dump())

        st.markdown("---")
        st.markdown("### 📚 Synthetic Invoice Corpus (Phase 2)")
        manifest_path = settings.data_dir / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = DatasetManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
                st.write(
                    f"**Corpus Status:** `{manifest.total_documents} total invoices` ("
                    f"`{manifest.digital_count} digital`, `{manifest.scanned_count} scanned/image-based`)"
                )
                st.write(f"**Random Generation Seed:** `{manifest.generation_seed}`")
                st.caption(
                    "All 50 synthetic documents are mapped to gold-standard annotations "
                    "in `data/annotations/` representing deliberate edge cases."
                )
            except Exception as e:
                st.warning(f"Could not load dataset manifest: {e}")

    with col2:
        st.markdown("### ⚙️ Environment & Ingestion Limits")
        st.write(f"**Python Version:** `{sys.version.split()[0]}`")
        st.write(f"**Log Level:** `{settings.log_level}`")
        st.write(f"**Max Upload Size:** `{settings.max_upload_size_mb} MB`")
        st.write(f"**Max Page Count:** `{settings.max_page_count}`")
        st.write(f"**Allow Encrypted PDFs:** `{settings.allow_encrypted_pdfs}`")
        st.write(f"**Storage Directory:** `{settings.storage_dir.name}`")
        st.write(
            f"**Tesseract Path:** `{'Configured' if settings.tesseract_cmd else 'System PATH'}`"
        )

        st.success("✅ Secure Ingestion & Synthetic Dataset ready for Phase 3.")


if __name__ == "__main__":
    main()
