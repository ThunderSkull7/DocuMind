"""DocuMind Streamlit Application - Entry Point.

Phase 3 foundation providing system diagnostics, synthetic corpus stats,
document ingestion, and hybrid extraction demonstration.
"""

import sys

import streamlit as st

from documind import __version__
from documind.config import get_settings
from documind.dataset.models import DatasetManifest
from documind.extraction.ocr import is_tesseract_available
from documind.extraction.service import ExtractionService
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
        f"**Phase 3 Active** — Hybrid PDF Text Extraction & OCR Pipeline | "
        f"Version {__version__} | Environment: `{settings.env}`"
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📥 Ingestion & Extraction Demonstration")
        st.caption(
            "Upload an invoice PDF to test validation, storage, and page-level hybrid extraction "
            "(PyMuPDF native text with automatic Tesseract OCR fallback)."
        )

        uploaded_file = st.file_uploader(
            "Select invoice PDF",
            type=["pdf"],
            help=f"Enforces maximum size of {settings.max_upload_size_mb} MB and PDF magic bytes inspection.",
        )

        if uploaded_file is not None:
            ingestion_svc = IngestionService()
            ingest_result = ingestion_svc.ingest(
                file_input=uploaded_file,
                original_filename=uploaded_file.name,
            )

            if ingest_result.success:
                doc_id = ingest_result.metadata.document_id
                st.success(
                    f"✅ Ingestion Successful! Internal ID: `{doc_id}` | "
                    f"Pages: `{ingest_result.metadata.page_count}` | "
                    f"SHA-256: `{ingest_result.metadata.sha256_hash[:16]}...`"
                )

                st.markdown("#### ⚙️ Extraction Output")
                extraction_svc = ExtractionService()
                extract_result = extraction_svc.extract_document(
                    document_id=doc_id,
                    expected_hash=ingest_result.metadata.sha256_hash,
                )

                st.write(
                    f"**Status:** `{extract_result.extraction_status.value}` | "
                    f"**Strategy:** `{extract_result.overall_extraction_method.value}` | "
                    f"**Duration:** `{extract_result.processing_duration_ms:.1f} ms`"
                )

                if extract_result.warnings:
                    for w in extract_result.warnings:
                        st.warning(f"⚠️ {w}")

                for page in extract_result.pages:
                    badge = (
                        "🟦 Native Vector Text"
                        if page.extraction_method.value == "native_text"
                        else "🟧 OCR Fallback"
                    )
                    with st.expander(
                        f"Page {page.page_number} — {badge} ({page.character_count} chars, {page.word_count} words)",
                        expanded=True,
                    ):
                        st.caption(
                            f"Page Dimensions: {page.page_width:.1f} x {page.page_height:.1f} pt"
                        )
                        st.text_area(
                            f"Normalized Text (Page {page.page_number})",
                            value=page.normalized_text,
                            height=200,
                            disabled=True,
                        )
                        if page.quality:
                            st.json(page.quality.signals)

            else:
                st.error(f"❌ Ingestion rejected: {ingest_result.error_message}")
                st.write("**Validation Details:**", ingest_result.metadata.validation.model_dump())

        st.markdown("---")
        st.markdown("### 📚 Synthetic Invoice Corpus (Phase 2 & 3)")
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
        st.markdown("### ⚙️ Environment & Extraction Diagnostics")
        st.write(f"**Python Version:** `{sys.version.split()[0]}`")
        st.write(f"**Log Level:** `{settings.log_level}`")
        st.write(f"**Max Upload Size:** `{settings.max_upload_size_mb} MB`")
        st.write(f"**Max Page Count:** `{settings.max_page_count}`")
        st.write(f"**OCR Enabled:** `{settings.ocr_enabled}`")
        st.write(f"**OCR Rendering DPI:** `{settings.ocr_dpi}`")
        st.write(
            f"**Tesseract Binary:** `{'Available' if is_tesseract_available(settings) else 'Not Found (PATH)'}`"
        )
        st.write(f"**Min Native Char Threshold:** `{settings.routing_min_char_count}`")

        if not is_tesseract_available(settings):
            st.warning(
                "Tesseract executable is not detected on PATH. "
                "Digital vector extraction is fully active; scanned PDFs will report OCR unavailable warnings."
            )
        else:
            st.success("✅ Tesseract OCR available for scanned image fallback.")


if __name__ == "__main__":
    main()
