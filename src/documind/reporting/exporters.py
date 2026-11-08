"""Reporting and export utilities generating structured CSV and JSON reports.

Produces verified processing summaries, validation reports, discrepancy logs,
review decisions, correction records, and chronological audit histories.
All CSV exports incorporate formula-injection sanitization.
"""

import csv
import io
import json
from typing import Any

from documind.reporting.csv_sanitizer import sanitize_csv_value
from documind.review.audit import AuditEvent
from documind.review.models import CorrectionStatus, ReviewRecord
from documind.schemas.invoice import InvoiceExtractionRecord
from documind.validation.models import ValidationResult


class ProcessingSummaryExporter:
    """Exports high-level ingestion, extraction, and validation metrics."""

    @staticmethod
    def to_dict(
        extractions: list[InvoiceExtractionRecord],
        validations: list[ValidationResult],
        reviews: list[ReviewRecord],
    ) -> dict[str, Any]:
        val_status_counts: dict[str, int] = {}
        for v in validations:
            val_status_counts[v.overall_status.value] = (
                val_status_counts.get(v.overall_status.value, 0) + 1
            )

        review_status_counts: dict[str, int] = {}
        for r in reviews:
            review_status_counts[r.status.value] = review_status_counts.get(r.status.value, 0) + 1

        return {
            "disclaimer": "This report is an internal operational summary and not a legally certified audit record.",
            "total_documents": len(extractions),
            "validation_status_breakdown": val_status_counts,
            "review_status_breakdown": review_status_counts,
            "total_discrepancies": sum(len(v.discrepancies) for v in validations),
            "total_reviews": len(reviews),
        }

    @classmethod
    def to_json(
        cls,
        extractions: list[InvoiceExtractionRecord],
        validations: list[ValidationResult],
        reviews: list[ReviewRecord],
    ) -> str:
        data = cls.to_dict(extractions, validations, reviews)
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def to_csv(
        extractions: list[InvoiceExtractionRecord],
        validations: list[ValidationResult],
        reviews: list[ReviewRecord],
    ) -> str:
        val_map = {v.document_id: v for v in validations}
        rev_map = {r.document_id: r for r in reviews}

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "document_id",
                "file_name",
                "invoice_number",
                "vendor_name",
                "currency",
                "total_amount",
                "validation_passed",
                "validation_status",
                "discrepancies_count",
                "review_status",
                "assigned_reviewer",
            ]
        )

        for ext in extractions:
            doc_id = ext.document_id
            val = val_map.get(doc_id)
            rev = rev_map.get(doc_id)

            val_status = val.overall_status.value if val else "NOT_VALIDATED"
            disc_count = len(val.discrepancies) if val else 0
            rev_status = rev.status.value if rev else "NO_REVIEW"
            assignee = rev.assigned_reviewer if rev and rev.assigned_reviewer else ""

            rf = ext.raw_fields
            writer.writerow(
                [
                    sanitize_csv_value(doc_id),
                    sanitize_csv_value(ext.file_name),
                    sanitize_csv_value(rf.get("invoice_number", "")),
                    sanitize_csv_value(rf.get("vendor_name", "")),
                    sanitize_csv_value(rf.get("currency", "")),
                    sanitize_csv_value(rf.get("total", "")),
                    sanitize_csv_value(ext.validation_passed),
                    sanitize_csv_value(val_status),
                    sanitize_csv_value(disc_count),
                    sanitize_csv_value(rev_status),
                    sanitize_csv_value(assignee),
                ]
            )

        return output.getvalue()


class DiscrepancyReportExporter:
    """Exports granular validation discrepancies across all documents."""

    @staticmethod
    def to_csv(validations: list[ValidationResult]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "document_id",
                "discrepancy_id",
                "rule_id",
                "rule_name",
                "category",
                "severity",
                "outcome",
                "affected_fields",
                "expected_value",
                "actual_value",
                "difference",
                "explanation",
                "review_recommendation",
            ]
        )

        for val in validations:
            for d in val.discrepancies:
                writer.writerow(
                    [
                        sanitize_csv_value(d.document_id),
                        sanitize_csv_value(d.discrepancy_id),
                        sanitize_csv_value(d.rule_id),
                        sanitize_csv_value(d.rule_name),
                        sanitize_csv_value(d.category.value),
                        sanitize_csv_value(d.severity.value),
                        sanitize_csv_value(d.outcome.value),
                        sanitize_csv_value(", ".join(d.affected_fields)),
                        sanitize_csv_value(d.expected_value),
                        sanitize_csv_value(d.actual_value),
                        sanitize_csv_value(d.difference),
                        sanitize_csv_value(d.explanation),
                        sanitize_csv_value(d.review_recommendation),
                    ]
                )

        return output.getvalue()

    @staticmethod
    def to_json(validations: list[ValidationResult]) -> str:
        all_discrepancies: list[dict[str, Any]] = []
        for val in validations:
            for d in val.discrepancies:
                all_discrepancies.append(d.model_dump(mode="json"))

        wrapper = {
            "disclaimer": "Internal validation discrepancy log. Not a legally certified audit report.",
            "total_discrepancies": len(all_discrepancies),
            "discrepancies": all_discrepancies,
        }
        return json.dumps(wrapper, indent=2, default=str)


class ReviewOutcomeExporter:
    """Exports human review decisions, corrections, and final status outcomes."""

    @staticmethod
    def to_csv(reviews: list[ReviewRecord]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "review_id",
                "document_id",
                "extraction_reference",
                "initial_validation_status",
                "current_review_status",
                "assigned_reviewer",
                "revision",
                "created_at",
                "updated_at",
                "completed_at",
                "total_decisions",
                "total_corrections",
                "accepted_corrections",
            ]
        )

        for rev in reviews:
            accepted_count = sum(
                1 for c in rev.corrections if c.status == CorrectionStatus.ACCEPTED
            )
            writer.writerow(
                [
                    sanitize_csv_value(rev.review_id),
                    sanitize_csv_value(rev.document_id),
                    sanitize_csv_value(rev.extraction_reference),
                    sanitize_csv_value(rev.initial_validation_status.value),
                    sanitize_csv_value(rev.status.value),
                    sanitize_csv_value(rev.assigned_reviewer or ""),
                    sanitize_csv_value(rev.revision),
                    sanitize_csv_value(rev.created_at.isoformat()),
                    sanitize_csv_value(rev.updated_at.isoformat()),
                    sanitize_csv_value(rev.completed_at.isoformat() if rev.completed_at else ""),
                    sanitize_csv_value(len(rev.decisions)),
                    sanitize_csv_value(len(rev.corrections)),
                    sanitize_csv_value(accepted_count),
                ]
            )

        return output.getvalue()

    @staticmethod
    def to_json(reviews: list[ReviewRecord]) -> str:
        records: list[dict[str, Any]] = []
        for rev in reviews:
            records.append(rev.model_dump(mode="json"))

        wrapper = {
            "disclaimer": "Internal human review workflow report. Not a legally certified audit report.",
            "total_reviews": len(records),
            "reviews": records,
        }
        return json.dumps(wrapper, indent=2, default=str)


class CorrectionHistoryExporter:
    """Exports detailed field-level correction proposals, reasons, and status changes."""

    @staticmethod
    def to_csv(reviews: list[ReviewRecord]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "correction_id",
                "review_id",
                "document_id",
                "field_name",
                "original_value",
                "corrected_value",
                "status",
                "reason",
                "reviewer",
                "is_reviewer_supplied",
                "evidence_references",
                "created_at",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
            ]
        )

        for rev in reviews:
            for corr in rev.corrections:
                writer.writerow(
                    [
                        sanitize_csv_value(corr.correction_id),
                        sanitize_csv_value(rev.review_id),
                        sanitize_csv_value(rev.document_id),
                        sanitize_csv_value(corr.field_name),
                        sanitize_csv_value(corr.original_value),
                        sanitize_csv_value(corr.corrected_value),
                        sanitize_csv_value(corr.status.value),
                        sanitize_csv_value(corr.reason),
                        sanitize_csv_value(corr.reviewer),
                        sanitize_csv_value(corr.is_reviewer_supplied),
                        sanitize_csv_value(", ".join(corr.evidence_references)),
                        sanitize_csv_value(corr.created_at.isoformat()),
                        sanitize_csv_value(corr.reviewed_by or ""),
                        sanitize_csv_value(
                            corr.reviewed_at.isoformat() if corr.reviewed_at else ""
                        ),
                        sanitize_csv_value(corr.rejection_reason or ""),
                    ]
                )

        return output.getvalue()


class AuditHistoryExporter:
    """Exports chronological, immutable audit event streams."""

    @staticmethod
    def to_csv(events: list[AuditEvent]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "event_id",
                "document_id",
                "review_id",
                "event_type",
                "actor",
                "timestamp",
                "previous_state",
                "new_state",
                "affected_fields",
                "discrepancy_ids",
                "details",
                "comment",
            ]
        )

        for evt in events:
            writer.writerow(
                [
                    sanitize_csv_value(evt.event_id),
                    sanitize_csv_value(evt.document_id),
                    sanitize_csv_value(evt.review_id),
                    sanitize_csv_value(evt.event_type.value),
                    sanitize_csv_value(evt.actor),
                    sanitize_csv_value(evt.timestamp.isoformat()),
                    sanitize_csv_value(evt.previous_state or ""),
                    sanitize_csv_value(evt.new_state or ""),
                    sanitize_csv_value(", ".join(evt.affected_fields)),
                    sanitize_csv_value(", ".join(evt.discrepancy_ids)),
                    sanitize_csv_value(json.dumps(evt.details) if evt.details else ""),
                    sanitize_csv_value(evt.comment or ""),
                ]
            )

        return output.getvalue()

    @staticmethod
    def to_json(events: list[AuditEvent]) -> str:
        serialized = [e.model_dump(mode="json") for e in events]
        wrapper = {
            "disclaimer": "Application-level append-only audit event log. Not hardware WORM or legally certified.",
            "total_events": len(serialized),
            "events": serialized,
        }
        return json.dumps(wrapper, indent=2, default=str)
