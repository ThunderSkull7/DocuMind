# ADR 0003: Hybrid PDF Text Extraction & OCR Pipeline

## Status
Accepted

## Context
Phase 3 requires a production-grade, modular document extraction subsystem that processes both native digital PDFs and scanned image-based PDFs without prematurely implementing invoice field extraction or business validation. The system must preserve reading order, word-level and block-level spatial bounding boxes, provide deterministic text normalization, and execute intelligent page-level hybrid routing.

## Decisions

1. **Page-Level Hybrid Routing Architecture**:
   Implement routing at the individual page level rather than whole-document level. For each page, PyMuPDF native vector extraction is evaluated against quality signals (`routing_min_char_count >= 50`, `routing_min_alpha_ratio >= 0.4`, `routing_min_word_count >= 5`). If sufficient, native extraction is retained with zero OCR overhead; if insufficient, OCR fallback is triggered automatically.

2. **Unified PDF Point Coordinate System**:
   All bounding boxes across native text and OCR use standard PDF point coordinates (`72 points = 1 inch`) with the origin `(0, 0)` anchored at the top-left corner. OCR raster pixel bounding boxes are projected to PDF points using scale ratios:
   $$x_{\text{pt}} = x_{\text{px}} \times \frac{\text{page\_width}}{\text{pixmap\_width}}, \quad y_{\text{pt}} = y_{\text{px}} \times \frac{\text{page\_height}}{\text{pixmap\_height}}$$

3. **Explicit Engine Confidence Model**:
   Native vector text extractions record `confidence = None` because digital PDF parsers extract raw encoded glyph streams without statistical probability modeling. Tesseract OCR extractions record normalized engine-reported confidence (`0.0` to `1.0`), explicitly distinguished from calibrated probabilistic confidence.

4. **Deterministic Safe Normalization**:
   Normalization unifies line breaks, removes unprintable ASCII control characters, and collapses horizontal whitespace while strictly preserving invoice identifiers (e.g. `INV-0O1I1lB8`), decimal separators (both dots and commas), and currency symbols. Original raw text is retained alongside normalized text.

5. **Environmental Blocker Handling for Tesseract**:
   If Tesseract OCR binary is absent on system PATH, the engine logs clear non-fatal warnings on scanned pages, preserves the empty native page container, and reports the exact Windows/Linux installation instructions rather than crashing or fabricating text.

## Consequences
- **Positive**: Clean separation between text extraction and invoice domain semantics; zero cloud API dependency; high performance on digital PDFs (average 2.67 ms/doc); resilient hybrid handling.
- **Negative**: Scanned document evaluation on local environments requires installing the Tesseract OCR binary.
