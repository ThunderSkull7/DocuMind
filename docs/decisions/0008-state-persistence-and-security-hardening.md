# ADR 0008: State Persistence Hardening, Snapshot Corruption Resilience & Evaluation Rigor

## Status
Accepted

## Date
2026-11-08

## Context
During the Phase 8 comprehensive technical audit, three critical reliability and evaluation gaps were identified:
1. **Persistence Incompleteness & Non-Atomic Writes**: `AppState` previously only persisted review records and audit events, omitting `extractions`, `validations`, `documents`, and `document_paths`. Writing files directly via `write_text` risked truncated or unparseable JSON files if the process was terminated mid-write. Moreover, corrupted files were silently swallowed without logging or recovery backups.
2. **Evaluation Conflation**: Phase 4 structured extraction evaluation previously counted correctly detected missing fields (True Negatives) in the numerator of extraction accuracy, inflating the reported extraction accuracy without distinguishing value extraction from missingness detection.
3. **CI Pipeline Incompleteness**: GitHub Actions CI lacked system-level Tesseract installation, causing integration tests on scanned PDFs to be skipped on remote runners.

## Decision

### 1. Atomic Persistence & Full Domain State Serialization (`app/services/state.py`)
- We extend `AppState.save_to_disk()` to serialize all active domain entities: `reviews.json`, `audit.json`, `extractions.json`, `validations.json`, `documents.json`, and `paths.json`.
- All writes are executed atomically via `_atomic_write_json()`, writing to a `.tmp` file and executing an atomic `os.replace`.
- In `_safe_load_json_file()`, if a JSON file fails to parse or is corrupted, it is automatically moved to `<filename>.corrupted_<timestamp>` for forensics, and logged with structured error alerts, allowing the application to recover safely.

### 2. Disaggregated Evaluation Metrics & Precision/Recall/F1 Matrix (`scripts/evaluate_extraction.py`)
- Extraction evaluation distinguishes True Positives (exact value match), False Positives, False Negatives, True Negatives (correctly detected missing), and Ambiguous fields.
- Precision, Recall, and F1 are computed and reported separately with explicit denominators for ground-truth present and absent fields.
- Explicit disclaimers document that OCR confidences are uncalibrated raw heuristic scores, and evaluation results reflect performance on the synthetic benchmark corpus rather than unconstrained real-world documents.

### 3. CI Hardening (`.github/workflows/ci.yml`)
- Added `sudo apt-get install -y tesseract-ocr tesseract-ocr-eng` to the Ubuntu GitHub Actions runner, ensuring all 20 scanned corpus documents and OCR integration tests run on remote CI.

## Consequences

### Positive
- Robust local state recovery across restarts and process interruptions.
- Corrupted state files are preserved for forensics rather than lost or silently ignored.
- Methodologically sound evaluation metrics with explicit denominators.
- Complete remote CI verification across all 50 corpus documents.

### Limitations
- File-based JSON persistence remains scoped for single-operator local use and workstation pilots. Multi-operator concurrent environments will transition persistence to PostgreSQL.

