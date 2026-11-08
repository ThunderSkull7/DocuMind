"""Synthetic dataset generation and gold-standard annotations for DocuMind."""

from documind.dataset.generator import SyntheticInvoiceGenerator, generate_dataset
from documind.dataset.models import (
    DatasetManifest,
    DocumentCharacteristics,
    DocumentType,
    IntroducedIssue,
    IssueType,
    ManifestDocumentEntry,
    SyntheticInvoiceAnnotation,
)

__all__ = [
    "DatasetManifest",
    "DocumentCharacteristics",
    "DocumentType",
    "IntroducedIssue",
    "IssueType",
    "ManifestDocumentEntry",
    "SyntheticInvoiceAnnotation",
    "SyntheticInvoiceGenerator",
    "generate_dataset",
]
