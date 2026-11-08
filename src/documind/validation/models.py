"""Domain models for business rule validation, discrepancies, and audit summaries.

Defines standardized data structures for validation outcomes, severities,
arithmetic checks, duplicate detection, and evidence-grounded discrepancy reporting.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from documind.schemas.invoice import FieldEvidence

UTC = timezone.utc


class ValidationOutcome(str, Enum):
    """Execution outcome of an individual business rule evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Severity(str, Enum):
    """Impact severity of a validation rule failure or warning."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RuleCategory(str, Enum):
    """Categorization of business and validation rules."""

    ARITHMETIC = "arithmetic"
    COMPLETENESS = "completeness"
    TEMPORAL = "temporal"
    FORMAT_AND_ENCODING = "format_and_encoding"
    DUPLICATE = "duplicate"
    REFERENCE_MATCH = "reference_match"
    BUSINESS_POLICY = "business_policy"


class OverallValidationStatus(str, Enum):
    """Document-level aggregated validation status."""

    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INVALID = "INVALID"
    INDETERMINATE = "INDETERMINATE"


class Discrepancy(BaseModel):
    """Structured discrepancy identifying a rule violation or inconsistency with grounding evidence."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    discrepancy_id: str = Field(
        ..., description="Unique deterministic identifier for this discrepancy"
    )
    document_id: str = Field(..., description="Document identifier associated with the discrepancy")
    rule_id: str = Field(..., description="Unique rule code (e.g. ARITH_001, BIZ_002)")
    rule_name: str = Field(..., description="Human-readable name of the evaluated rule")
    category: RuleCategory = Field(..., description="Classification category")
    severity: Severity = Field(..., description="Discrepancy impact severity")
    outcome: ValidationOutcome = Field(
        ..., description="Evaluation outcome: FAIL, WARNING, INDETERMINATE"
    )
    affected_fields: list[str] = Field(
        default_factory=list, description="List of schema fields involved in this discrepancy"
    )
    expected_value: Any = Field(
        default=None, description="Expected value if mathematically or logically known"
    )
    actual_value: Any = Field(
        default=None, description="Actual extracted value found on the document"
    )
    difference: Any = Field(
        default=None, description="Calculated variance or numerical delta where applicable"
    )
    explanation: str = Field(..., description="Clear human-readable explanation of the discrepancy")
    evidence_references: list[str] = Field(
        default_factory=list, description="Keys of relevant fields in the document evidence map"
    )
    evidence_snippets: list[FieldEvidence] = Field(
        default_factory=list,
        description="Grounding evidence records with coordinates and source provenance",
    )
    review_recommendation: str = Field(
        default="", description="Actionable recommendation for human reviewer or automated routing"
    )


class DuplicateMatchType(str, Enum):
    """Classification of duplicate invoice relationship."""

    NONE = "none"
    EXACT_HASH = "exact_hash"
    EXACT_IDENTITY = "exact_identity"
    POTENTIAL_MATCH = "potential_match"


class DuplicateCheckResult(BaseModel):
    """Outcome of duplicate invoice screening across corpus or history."""

    model_config = ConfigDict(extra="forbid")

    is_duplicate: bool = Field(
        default=False, description="True if document is a confirmed or potential duplicate"
    )
    match_type: DuplicateMatchType = Field(
        default=DuplicateMatchType.NONE, description="Type of duplicate match"
    )
    matching_document_ids: list[str] = Field(
        default_factory=list, description="Identifiers of matching documents"
    )
    similarity_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Heuristic similarity score (uncalibrated)"
    )
    explanation: str = Field(
        default="No duplicate identified", description="Rationale for duplicate assessment"
    )
    recommendation: str = Field(
        default="Proceed with standard processing", description="Review recommendation"
    )


class VendorMasterRecord(BaseModel):
    """Optional reference master record for vendor verification."""

    model_config = ConfigDict(extra="forbid")

    vendor_id: str = Field(..., description="Internal master data vendor code")
    name: str = Field(..., description="Official legal entity corporate name")
    tax_id: str | None = Field(default=None, description="Registered corporate tax/VAT number")
    address: str | None = Field(default=None, description="Registered address")
    default_currency: str | None = Field(default=None, description="Standard invoicing currency")


class PurchaseOrderReference(BaseModel):
    """Optional reference purchase order record."""

    model_config = ConfigDict(extra="forbid")

    po_number: str = Field(..., description="Purchase order reference number")
    vendor_name: str = Field(..., description="Expected vendor corporate name")
    expected_total: str = Field(..., description="Approved purchase order total amount")
    currency: str = Field(..., description="Expected currency code")


class ReferenceMatchStatus(str, Enum):
    """Outcome of matching against reference master data."""

    EXACT = "exact"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    NOT_PROVIDED = "not_provided"


class ReferenceMatchResult(BaseModel):
    """Outcome of validating extracted entities against reference records."""

    model_config = ConfigDict(extra="forbid")

    vendor_match_status: ReferenceMatchStatus = Field(
        default=ReferenceMatchStatus.NOT_PROVIDED, description="Vendor reference match status"
    )
    po_match_status: ReferenceMatchStatus = Field(
        default=ReferenceMatchStatus.NOT_PROVIDED,
        description="Purchase order reference match status",
    )
    matched_vendor_id: str | None = Field(default=None, description="Matched vendor ID if found")
    details: str = Field(
        default="No reference data supplied", description="Detailed match explanation"
    )


class ValidationResult(BaseModel):
    """Comprehensive document-level validation outcome and discrepancy report."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    document_id: str = Field(..., description="Document identifier")
    overall_status: OverallValidationStatus = Field(..., description="Aggregate validation status")
    rules_evaluated: int = Field(default=0, ge=0, description="Total rules evaluated")
    rules_passed: int = Field(default=0, ge=0, description="Total rules passed cleanly")
    rules_failed: int = Field(default=0, ge=0, description="Total rules failed")
    rules_warning: int = Field(default=0, ge=0, description="Total rules resulting in warnings")
    rules_indeterminate: int = Field(
        default=0, ge=0, description="Total rules with insufficient data"
    )
    discrepancies: list[Discrepancy] = Field(
        default_factory=list, description="All identified discrepancies"
    )
    duplicate_check: DuplicateCheckResult | None = Field(
        default=None, description="Duplicate screening results"
    )
    reference_check: ReferenceMatchResult | None = Field(
        default=None, description="Reference data reconciliation results"
    )
    recommended_action: str = Field(..., description="Actionable pipeline routing recommendation")
    evaluation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp of validation evaluation"
    )
