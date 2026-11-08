"""Empirical performance benchmarking script for DocuMind.

Measures:
1. Digital PDF native extraction latency.
2. Scanned PDF OCR extraction latency.
3. Structured field extraction latency.
4. Business validation latency.
5. End-to-end processing latency per document.
6. Memory consumption profile.
"""

import json
import platform
import time
import tracemalloc
from pathlib import Path
from statistics import mean, median

from documind import __version__
from documind.config import get_settings
from documind.extraction.field_extractor import StructuredInvoiceExtractor
from documind.extraction.ocr import resolve_tesseract_cmd
from documind.extraction.service import ExtractionService
from documind.validation.service import ValidationService


def run_benchmark() -> dict:
    settings = get_settings()
    manifest_path = Path("data/manifest.json")
    if not manifest_path.is_file():
        raise FileNotFoundError("data/manifest.json not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ext_service = ExtractionService(settings=settings)
    field_extractor = StructuredInvoiceExtractor()
    val_service = ValidationService()

    digital_entries = [d for d in manifest["documents"] if d["document_type"] == "digital"]
    scanned_entries = [d for d in manifest["documents"] if d["document_type"] == "scanned"]

    tracemalloc.start()
    start_wall_time = time.perf_counter()

    digital_raw_ms = []
    digital_struct_ms = []
    digital_val_ms = []
    digital_e2e_ms = []

    print(f"Benchmarking {len(digital_entries)} digital invoices...")
    for entry in digital_entries:
        pdf_bytes = (Path("data/synthetic_documents") / entry["file_name"]).read_bytes()

        t0 = time.perf_counter()
        raw_res = ext_service.extract_from_bytes(
            pdf_bytes, entry["document_id"], entry["sha256_hash"]
        )
        t1 = time.perf_counter()
        record = field_extractor.extract(raw_res, entry["file_name"])
        t2 = time.perf_counter()
        _ = val_service.validate_record(record, entry["sha256_hash"])
        t3 = time.perf_counter()

        digital_raw_ms.append((t1 - t0) * 1000.0)
        digital_struct_ms.append((t2 - t1) * 1000.0)
        digital_val_ms.append((t3 - t2) * 1000.0)
        digital_e2e_ms.append((t3 - t0) * 1000.0)

    scanned_raw_ms = []
    scanned_struct_ms = []
    scanned_val_ms = []
    scanned_e2e_ms = []

    print(f"Benchmarking {len(scanned_entries)} scanned invoices (with local OCR)...")
    for entry in scanned_entries:
        pdf_bytes = (Path("data/synthetic_documents") / entry["file_name"]).read_bytes()

        t0 = time.perf_counter()
        raw_res = ext_service.extract_from_bytes(
            pdf_bytes, entry["document_id"], entry["sha256_hash"]
        )
        t1 = time.perf_counter()
        record = field_extractor.extract(raw_res, entry["file_name"])
        t2 = time.perf_counter()
        _ = val_service.validate_record(record, entry["sha256_hash"])
        t3 = time.perf_counter()

        scanned_raw_ms.append((t1 - t0) * 1000.0)
        scanned_struct_ms.append((t2 - t1) * 1000.0)
        scanned_val_ms.append((t3 - t2) * 1000.0)
        scanned_e2e_ms.append((t3 - t0) * 1000.0)

    total_wall_sec = time.perf_counter() - start_wall_time
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    results = {
        "metadata": {
            "version": __version__,
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
            "processor": platform.processor(),
            "tesseract_cmd": resolve_tesseract_cmd(settings),
            "sample_size": len(manifest["documents"]),
            "digital_count": len(digital_entries),
            "scanned_count": len(scanned_entries),
            "total_wall_duration_sec": round(total_wall_sec, 2),
            "peak_memory_mb": round(peak_mem / (1024 * 1024), 2),
        },
        "digital": {
            "native_text_mean_ms": round(mean(digital_raw_ms), 2),
            "native_text_median_ms": round(median(digital_raw_ms), 2),
            "structured_field_mean_ms": round(mean(digital_struct_ms), 2),
            "validation_mean_ms": round(mean(digital_val_ms), 2),
            "e2e_mean_ms": round(mean(digital_e2e_ms), 2),
            "e2e_median_ms": round(median(digital_e2e_ms), 2),
        },
        "scanned": {
            "ocr_text_mean_ms": round(mean(scanned_raw_ms), 2),
            "ocr_text_median_ms": round(median(scanned_raw_ms), 2),
            "structured_field_mean_ms": round(mean(scanned_struct_ms), 2),
            "validation_mean_ms": round(mean(scanned_val_ms), 2),
            "e2e_mean_ms": round(mean(scanned_e2e_ms), 2),
            "e2e_median_ms": round(median(scanned_e2e_ms), 2),
        },
    }

    print("\n--- DocuMind Empirical Performance Summary ---")
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run_benchmark()
