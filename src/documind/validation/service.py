"""Validation orchestration service coordinating arithmetic, business rules, and discrepancies."""

from datetime import UTC, datetime

from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.arithmetic import ArithmeticValidator
from documind.validation.business_rules import BusinessRulesValidator
from documind.validation.duplicate_detection import DuplicateDetector
from documind.validation.models import (
    Discrepancy,
    OverallValidationStatus,
    Severity,
    ValidationOutcome,
    ValidationResult,
)
from documind.validation.reference_matching import ReferenceMatcher


class ValidationService:
    """Orchestrates comprehensive business rule validation, arithmetic checks, and discrepancy reporting."""

    def __init__(
        self,
        arithmetic_validator: ArithmeticValidator | None = None,
        business_rules_validator: BusinessRulesValidator | None = None,
        duplicate_detector: DuplicateDetector | None = None,
        reference_matcher: ReferenceMatcher | None = None,
    ) -> None:
        self.arithmetic = arithmetic_validator or ArithmeticValidator()
        self.business_rules = business_rules_validator or BusinessRulesValidator()
        self.duplicates = duplicate_detector or DuplicateDetector()
        self.references = reference_matcher or ReferenceMatcher()

    def validate_record(
        self,
        record: InvoiceExtractionRecord,
        source_hash: str | None = None,
    ) -> ValidationResult:
        """Execute all business validation rules against an extracted invoice record.

        Args:
            record: Structured InvoiceExtractionRecord produced in Phase 4.
            source_hash: Optional SHA-256 hash of the original document.

        Returns:
            ValidationResult with aggregated status, counts, and explainable discrepancies.
        """
        all_discrepancies: list[Discrepancy] = []

        # 1. Execute Arithmetic Validation
        arith_disc = self.arithmetic.validate(record)
        all_discrepancies.extend(arith_disc)

        # 2. Execute Business Rules Validation
        biz_disc = self.business_rules.validate(record)
        all_discrepancies.extend(biz_disc)

        # 3. Screen for Duplicate Invoices
        dup_result, dup_disc = self.duplicates.check_duplicate(record, source_hash=source_hash)
        if dup_disc:
            all_discrepancies.append(dup_disc)

        # 4. Reconcile with Reference Master Data
        ref_result, ref_disc = self.references.match(record)
        all_discrepancies.extend(ref_disc)

        # 5. Compute Validation Counts
        failed_count = sum(1 for d in all_discrepancies if d.outcome == ValidationOutcome.FAIL)
        warning_count = sum(1 for d in all_discrepancies if d.outcome == ValidationOutcome.WARNING)
        indet_count = sum(
            1 for d in all_discrepancies if d.outcome == ValidationOutcome.INDETERMINATE
        )

        # Standard rule baseline: 6 arithmetic + 8 business + 2 duplicate + 3 reference = 19 rules
        total_rules_evaluated = 19
        passed_count = max(0, total_rules_evaluated - (failed_count + warning_count + indet_count))

        # 6. Aggregate Overall Validation Status
        overall_status: OverallValidationStatus
        recommended_action: str

        has_critical_failure = any(
            d.outcome == ValidationOutcome.FAIL and d.severity == Severity.CRITICAL
            for d in all_discrepancies
        )
        has_high_failure = any(
            d.outcome == ValidationOutcome.FAIL and d.severity in {Severity.HIGH, Severity.MEDIUM}
            for d in all_discrepancies
        )
        has_high_indeterminate = any(
            d.outcome == ValidationOutcome.INDETERMINATE
            and d.severity in {Severity.CRITICAL, Severity.HIGH}
            for d in all_discrepancies
        )

        if has_critical_failure:
            overall_status = OverallValidationStatus.INVALID
            recommended_action = (
                "Reject invoice or request corrected replacement from billing vendor."
            )
        elif has_high_failure or dup_result.is_duplicate:
            overall_status = OverallValidationStatus.NEEDS_REVIEW
            recommended_action = (
                "Route to human accounts payable review queue for exception resolution."
            )
        elif has_high_indeterminate:
            overall_status = OverallValidationStatus.INDETERMINATE
            recommended_action = "Manual inspection required to obtain unstated billing details."
        elif warning_count > 0:
            overall_status = OverallValidationStatus.VALID_WITH_WARNINGS
            recommended_action = "Approve invoice with recorded non-fatal audit warnings."
        else:
            overall_status = OverallValidationStatus.VALID
            recommended_action = "Approve invoice for automatic payment dispatch."

        return ValidationResult(
            document_id=record.document_id,
            overall_status=overall_status,
            rules_evaluated=total_rules_evaluated,
            rules_passed=passed_count,
            rules_failed=failed_count,
            rules_warning=warning_count,
            rules_indeterminate=indet_count,
            discrepancies=all_discrepancies,
            duplicate_check=dup_result,
            reference_check=ref_result,
            recommended_action=recommended_action,
            evaluation_timestamp=datetime.now(UTC),
        )
