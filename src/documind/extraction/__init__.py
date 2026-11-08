"""Extraction module for DocuMind.

Architectural Responsibility:
- Extract native text and word bounding boxes from digital PDF documents (via PyMuPDF).
- Detect scanned or image-based pages and invoke OCR fallback (via Tesseract).
- Normalize extracted text streams and spatial coordinate tokens.
- Implement structured field extraction strategies for invoice fields.
- Generate grounding evidence for each extracted field.

Implementation is scheduled for Phase 3.
"""

__all__: list[str] = []
