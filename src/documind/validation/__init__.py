"""Validation module for DocuMind.

Provides comprehensive arithmetic consistency validation, business rules,
duplicate screening, reference reconciliation, and structured discrepancy reporting.
"""

from documind.validation.arithmetic import ArithmeticValidator
from documind.validation.business_rules import BusinessRulesValidator
from documind.validation.duplicate_detection import DuplicateDetector
from documind.validation.models import (
    Discrepancy,
    DuplicateCheckResult,
    DuplicateMatchType,
    OverallValidationStatus,
    PurchaseOrderReference,
    ReferenceMatchResult,
    ReferenceMatchStatus,
    RuleCategory,
    Severity,
    ValidationOutcome,
    ValidationResult,
    VendorMasterRecord,
)
from documind.validation.reference_matching import (
    ReferenceMatcher,
    get_default_po_database,
    get_default_vendor_master,
)
from documind.validation.service import ValidationService

__all__ = [
    "ArithmeticValidator",
    "BusinessRulesValidator",
    "Discrepancy",
    "DuplicateCheckResult",
    "DuplicateDetector",
    "DuplicateMatchType",
    "OverallValidationStatus",
    "PurchaseOrderReference",
    "ReferenceMatchResult",
    "ReferenceMatchStatus",
    "ReferenceMatcher",
    "RuleCategory",
    "Severity",
    "ValidationOutcome",
    "ValidationResult",
    "ValidationService",
    "VendorMasterRecord",
    "get_default_po_database",
    "get_default_vendor_master",
]
