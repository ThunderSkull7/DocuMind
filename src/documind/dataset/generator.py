"""Synthetic invoice dataset generator for DocuMind.

Produces 50 deterministic synthetic invoices (30 digital, 20 scanned) with
ground-truth annotations, deliberate challenging edge cases, and manifest catalog.
"""

import hashlib
import io
import random
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pymupdf
from PIL import Image, ImageEnhance

from documind.config import get_settings
from documind.dataset.models import (
    DatasetManifest,
    DocumentCharacteristics,
    DocumentType,
    IntroducedIssue,
    IssueType,
    ManifestDocumentEntry,
    SyntheticInvoiceAnnotation,
)
from documind.logging import get_logger

UTC = timezone.utc
logger = get_logger("dataset.generator")

# Fictional vendor master data (completely synthetic)
FICTIONAL_VENDORS = [
    {
        "name": "Apex Cloud Systems Inc.",
        "address": "100 Innovation Way, Suite 400, San Jose, CA 95110",
        "tax_id": "US-EIN-94-3829102",
        "iban": None,
        "email": "billing@apexcloud.example",
    },
    {
        "name": "Beacon Logistics GmbH",
        "address": "Industriestrasse 42, 60311 Frankfurt am Main, Germany",
        "tax_id": "DE-VAT-194820194",
        "iban": "DE89370400440532013000",
        "email": "invoices@beacon-logistics.example",
    },
    {
        "name": "Crestview Media Solutions Ltd.",
        "address": "15 Soho Square, London W1D 3QL, United Kingdom",
        "tax_id": "GB-VAT-982-1049-33",
        "iban": "GB29NWBK60161331926819",
        "email": "accounts@crestviewmedia.example",
    },
    {
        "name": "Delta Office Furnishings Co.",
        "address": "742 Evergreen Terrace, Springfield, OR 97477",
        "tax_id": "US-EIN-55-9102847",
        "iban": None,
        "email": "finance@deltafurnishings.example",
    },
    {
        "name": "Epsilon Software Labs",
        "address": "88 Silicon Alley, 9th Floor, New York, NY 10010",
        "tax_id": "US-EIN-12-3498172",
        "iban": None,
        "email": "ar@epsilonlabs.example",
    },
    {
        "name": "Fjord Nordic Maritime Services",
        "address": "Havnegata 12, 0150 Oslo, Norway",
        "tax_id": "NO-MVA-918273645",
        "iban": "NO9386011117947",
        "email": "billing@fjordmaritime.example",
    },
]

FICTIONAL_CUSTOMERS = [
    {"name": "OmniCorp Global LLC", "address": "1200 Enterprise Blvd, Chicago, IL 60601"},
    {"name": "Vertex Holdings Ltd.", "address": "40 Bank Street, Canary Wharf, London E14 5NR"},
    {"name": "Nexus Dynamics B.V.", "address": "Keizersgracht 421, 1016 EK Amsterdam"},
    {"name": "Horizon Retailers Inc.", "address": "500 Commercial Way, Austin, TX 78701"},
]

FICTIONAL_LINE_ITEMS = [
    ("Cloud Server Compute (vCPU hours)", Decimal("120.00"), 2),
    ("Database Managed Storage (TB/month)", Decimal("85.50"), 1),
    ("Network Egress Traffic (GB)", Decimal("45.00"), 3),
    ("Senior Software Engineering Consultation", Decimal("175.00"), 4),
    ("Security & Compliance Audit Service", Decimal("450.00"), 1),
    ("Annual SaaS Enterprise License", Decimal("1200.00"), 1),
    ("Office Ergonomic Chairs - Series X", Decimal("220.00"), 2),
    ("Fiber Internet Dedicated Bandwidth", Decimal("350.00"), 1),
    ("Logistics Freight Dispatch Fee", Decimal("180.00"), 2),
    ("Data Warehouse ETL Processing", Decimal("210.00"), 1),
]


class SyntheticInvoiceGenerator:
    """Deterministic generator producing 50 synthetic invoices and annotations."""

    def __init__(
        self,
        seed: int = 42,
        output_dir: Path | None = None,
        annotations_dir: Path | None = None,
        manifest_path: Path | None = None,
    ) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        settings = get_settings()
        self.output_dir = output_dir or settings.synthetic_data_dir
        self.annotations_dir = annotations_dir or settings.annotations_dir
        self.manifest_path = manifest_path or (settings.data_dir / "manifest.json")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.annotations_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def generate_corpus(self) -> DatasetManifest:
        """Generate complete 50-document synthetic invoice corpus."""
        logger.info(f"Starting deterministic synthetic invoice generation (seed={self.seed})...")
        entries: list[ManifestDocumentEntry] = []

        # Generate 30 Digital PDFs (Index 1 to 30)
        for idx in range(1, 31):
            doc_id = f"DOC-SYN-{idx:03d}"
            entry = self._generate_invoice(idx, doc_id, doc_type=DocumentType.DIGITAL)
            entries.append(entry)

        # Generate 20 Scanned PDFs (Index 31 to 50)
        for idx in range(31, 51):
            doc_id = f"DOC-SYN-{idx:03d}"
            entry = self._generate_invoice(idx, doc_id, doc_type=DocumentType.SCANNED)
            entries.append(entry)

        manifest = DatasetManifest(
            dataset_version="1.0.0",
            created_at=datetime.now(UTC),
            generation_seed=self.seed,
            total_documents=len(entries),
            digital_count=30,
            scanned_count=20,
            documents=entries,
        )

        # Write manifest file
        self.manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        logger.info(
            f"Successfully generated {len(entries)} invoices. Manifest: {self.manifest_path}"
        )
        return manifest

    def _generate_invoice(
        self,
        index: int,
        document_id: str,
        doc_type: DocumentType,
    ) -> ManifestDocumentEntry:
        """Create a single invoice document with paired annotation and characteristics."""
        vendor_data = FICTIONAL_VENDORS[(index + self.seed) % len(FICTIONAL_VENDORS)]
        customer_data = FICTIONAL_CUSTOMERS[(index * 3) % len(FICTIONAL_CUSTOMERS)]

        # Layout assignment
        layouts = [
            "modern_tech",
            "corporate_classic",
            "telecom_utility",
            "professional_services",
            "european_vat",
        ]
        layout = layouts[(index - 1) % len(layouts)]

        # Determine page count: index 10 and 28 are multipage digital
        page_count = 2 if index in {10, 28} else 1

        # Base financial values
        item1 = FICTIONAL_LINE_ITEMS[(index) % len(FICTIONAL_LINE_ITEMS)]
        item2 = FICTIONAL_LINE_ITEMS[(index + 3) % len(FICTIONAL_LINE_ITEMS)]
        subtotal = (item1[1] * item1[2]) + (item2[1] * item2[2])
        tax_rate = Decimal("0.10")  # 10%
        tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
        total = subtotal + tax

        # Currency selection
        currencies = ["USD", "EUR", "GBP"]
        currency = (
            "EUR"
            if layout == "european_vat"
            else currencies[(index + (1 if doc_type == DocumentType.SCANNED else 0)) % 3]
        )

        # Base date
        inv_date = date(2024, ((index % 12) + 1), ((index * 2) % 25) + 1)
        invoice_date_str = inv_date.isoformat()
        invoice_number_str = f"INV-2024-{index:04d}"
        vendor_name_str = vendor_data["name"]

        # Track deliberately introduced challenges
        issues: list[IntroducedIssue] = []

        # Scanned characteristics defaults
        is_scanned = doc_type == DocumentType.SCANNED
        resolution_dpi = 300
        rotation_degrees = 0.0
        jpeg_quality = 85 if is_scanned else None
        contrast_factor = 1.0

        # Inject controlled variations and deliberate challenging cases
        if index == 7:  # Missing invoice number
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.MISSING_FIELD,
                    field="invoice_number",
                    description="Invoice number omitted intentionally from document header",
                    expected_extracted=None,
                    ground_truth_actual=None,
                )
            )
            invoice_number_str = None

        elif index == 12:  # Missing tax
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.MISSING_FIELD,
                    field="tax",
                    description="Tax amount omitted; tax is zero or exempt",
                    expected_extracted=None,
                    ground_truth_actual=None,
                )
            )
            tax = None
            total = subtotal

        elif index == 15:  # Arithmetic mismatch
            actual_math_total = total
            erroneous_total = total + Decimal("50.00")
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.ARITHMETIC_MISMATCH,
                    field="total",
                    description="Total amount on document intentionally does not equal subtotal + tax",
                    expected_extracted=f"{erroneous_total:.2f}",
                    ground_truth_actual=f"{actual_math_total:.2f}",
                )
            )
            total = erroneous_total

        elif index == 18:  # Missing vendor name
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.MISSING_FIELD,
                    field="vendor_name",
                    description="Vendor corporate entity name omitted from header",
                    expected_extracted=None,
                    ground_truth_actual=None,
                )
            )
            vendor_name_str = None

        elif index == 23:  # Ambiguous date format (03/04/2024)
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.AMBIGUOUS_DATE,
                    field="invoice_date",
                    description="Date formatted as 03/04/2024 (ambiguous between March 4 and April 3)",
                    expected_extracted="03/04/2024",
                    ground_truth_actual="2024-03-04",
                )
            )

        elif index == 25:  # Inconsistent dates
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.INCONSISTENT_DATES,
                    field="invoice_date",
                    description="Invoice issuance date is after the stated payment due date",
                    expected_extracted=invoice_date_str,
                    ground_truth_actual=invoice_date_str,
                )
            )

        elif index == 27:  # Unusual number formatting (European: 1.450,50)
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.UNUSUAL_NUMBER_FORMAT,
                    field="total",
                    description="Monetary values formatted with dots for thousands and comma for decimal",
                    expected_extracted=f"{total:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                    ground_truth_actual=f"{total:.2f}",
                )
            )

        elif index == 29:  # Similar looking characters (0 vs O, 1 vs I vs l)
            confusing_id = "INV-0O1I1lB8"
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.SIMILAR_LOOKING_CHARS,
                    field="invoice_number",
                    description="Invoice identifier deliberately mixes visually confusable glyphs (0, O, 1, I, l)",
                    expected_extracted=confusing_id,
                    ground_truth_actual=confusing_id,
                )
            )
            invoice_number_str = confusing_id

        elif index in {30, 45}:  # Duplicate invoice number across 2 docs
            dup_id = "INV-2024-DUP999"
            issues.append(
                IntroducedIssue(
                    issue_type=IssueType.DUPLICATE_IDENTIFIER,
                    field="invoice_number",
                    description="Shared duplicate invoice number identifier between DOC-SYN-030 and DOC-SYN-045",
                    expected_extracted=dup_id,
                    ground_truth_actual=dup_id,
                )
            )
            invoice_number_str = dup_id

        # Scanned-specific edge cases (Index 31 to 50)
        if doc_type == DocumentType.SCANNED:
            # Vary resolution, skew, and compression
            resolution_dpi = 150 if index % 3 == 0 else (200 if index % 2 == 0 else 300)
            rotation_degrees = -2.5 if index % 4 == 1 else (1.8 if index % 4 == 2 else 0.5)
            jpeg_quality = 45 if index % 5 == 0 else (65 if index % 2 == 0 else 80)
            contrast_factor = 0.85 if index % 6 == 0 else 1.05

            if abs(rotation_degrees) > 0.0:
                issues.append(
                    IntroducedIssue(
                        issue_type=IssueType.SCAN_SKEW,
                        field=None,
                        description=f"Scanned page rotated with {rotation_degrees:.1f} degrees skew",
                        expected_extracted=None,
                        ground_truth_actual=None,
                    )
                )

            if jpeg_quality < 60 or resolution_dpi <= 150:
                issues.append(
                    IntroducedIssue(
                        issue_type=IssueType.SCAN_DEGRADATION,
                        field=None,
                        description=f"Degraded image quality: DPI={resolution_dpi}, JPEG quality={jpeg_quality}",
                        expected_extracted=None,
                        ground_truth_actual=None,
                    )
                )

            if index == 35:  # Missing invoice number in scanned
                issues.append(
                    IntroducedIssue(
                        issue_type=IssueType.MISSING_FIELD,
                        field="invoice_number",
                        description="Scanned invoice with omitted invoice number header",
                        expected_extracted=None,
                        ground_truth_actual=None,
                    )
                )
                invoice_number_str = None

            elif index == 38:  # Missing tax in scanned
                issues.append(
                    IntroducedIssue(
                        issue_type=IssueType.MISSING_FIELD,
                        field="tax",
                        description="Scanned invoice with zero/omitted tax breakdown",
                        expected_extracted=None,
                        ground_truth_actual=None,
                    )
                )
                tax = None
                total = subtotal

            elif index == 41:  # Arithmetic mismatch in scanned
                actual_math_total = total
                erroneous_total = total + Decimal("100.00")
                issues.append(
                    IntroducedIssue(
                        issue_type=IssueType.ARITHMETIC_MISMATCH,
                        field="total",
                        description="Scanned invoice arithmetic mismatch (subtotal + tax != total)",
                        expected_extracted=f"{erroneous_total:.2f}",
                        ground_truth_actual=f"{actual_math_total:.2f}",
                    )
                )
                total = erroneous_total

        characteristics = DocumentCharacteristics(
            layout_template=layout,
            page_count=page_count,
            is_scanned=is_scanned,
            resolution_dpi=resolution_dpi,
            rotation_degrees=rotation_degrees,
            jpeg_quality=jpeg_quality,
            contrast_factor=contrast_factor,
        )

        # Generate Digital Vector Document
        digital_doc = self._render_digital_pdf(
            vendor=vendor_data if vendor_name_str else None,
            customer=customer_data,
            invoice_number=invoice_number_str,
            invoice_date=invoice_date_str,
            currency=currency,
            subtotal=subtotal,
            tax=tax,
            total=total,
            layout=layout,
            page_count=page_count,
            items=[item1, item2],
            index=index,
        )

        filename = f"syn_invoice_{index:03d}_{doc_type.value}.pdf"
        target_path = self.output_dir / filename

        if doc_type == DocumentType.DIGITAL:
            digital_doc.save(str(target_path), deflate=True, clean=True, no_new_id=True)
            digital_doc.close()
        else:
            # Convert digital PDF to scanned image-only PDF
            scanned_doc = self._convert_to_scanned_pdf(
                digital_doc=digital_doc,
                characteristics=characteristics,
            )
            digital_doc.close()
            scanned_doc.save(str(target_path), deflate=True, clean=True, no_new_id=True)
            scanned_doc.close()

        # Compute SHA-256
        file_bytes = target_path.read_bytes()
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        # Build Gold-Standard Annotation
        annotation = SyntheticInvoiceAnnotation(
            document_id=document_id,
            file_name=filename,
            document_type=doc_type,
            invoice_number=invoice_number_str,
            invoice_date=invoice_date_str,
            vendor_name=vendor_name_str,
            currency=currency,
            subtotal=f"{subtotal:.2f}" if subtotal is not None else None,
            tax=f"{tax:.2f}" if tax is not None else None,
            total=f"{total:.2f}" if total is not None else None,
            characteristics=characteristics,
            deliberately_introduced_issues=issues,
        )

        annotation_file = self.annotations_dir / f"{document_id}.json"
        annotation_file.write_text(annotation.model_dump_json(indent=2), encoding="utf-8")

        rel_doc_path = str(target_path.relative_to(self.output_dir.parents[1])).replace("\\", "/")
        rel_ann_path = str(annotation_file.relative_to(self.annotations_dir.parents[1])).replace(
            "\\", "/"
        )

        return ManifestDocumentEntry(
            document_id=document_id,
            file_name=filename,
            relative_path=rel_doc_path,
            annotation_path=rel_ann_path,
            sha256_hash=sha256_hash,
            document_type=doc_type,
            page_count=page_count,
            characteristics=characteristics,
            issues_count=len(issues),
        )

    def _render_digital_pdf(
        self,
        vendor: dict | None,
        customer: dict,
        invoice_number: str | None,
        invoice_date: str,
        currency: str,
        subtotal: Decimal,
        tax: Decimal | None,
        total: Decimal,
        layout: str,
        page_count: int,
        items: list,
        index: int,
    ) -> pymupdf.Document:
        """Render vector text PDF with layout styling."""
        doc = pymupdf.open()
        width, height = 595.0, 842.0  # A4

        for p_idx in range(page_count):
            page = doc.new_page(width=width, height=height)

            # Header / Banner Styling
            if layout == "modern_tech":
                page.draw_rect(pymupdf.Rect(0, 0, width, 80), color=None, fill=(0.12, 0.25, 0.45))
                page.insert_text(
                    pymupdf.Point(40, 50),
                    "INVOICE",
                    fontsize=26,
                    color=(1, 1, 1),
                    fontname="helv",
                )
                if vendor:
                    page.insert_text(
                        pymupdf.Point(320, 42),
                        vendor["name"],
                        fontsize=14,
                        color=(1, 1, 1),
                        fontname="helv",
                    )
            elif layout == "corporate_classic":
                page.draw_line(
                    pymupdf.Point(40, 75),
                    pymupdf.Point(width - 40, 75),
                    color=(0.2, 0.2, 0.2),
                    width=1.5,
                )
                page.insert_text(
                    pymupdf.Point(40, 60),
                    "TAX INVOICE",
                    fontsize=22,
                    color=(0.1, 0.1, 0.1),
                    fontname="times-bold",
                )
                if vendor:
                    page.insert_text(
                        pymupdf.Point(width - 240, 50),
                        vendor["name"],
                        fontsize=12,
                        color=(0.2, 0.2, 0.2),
                        fontname="times-roman",
                    )
            else:
                page.insert_text(
                    pymupdf.Point(40, 60),
                    "COMMERCIAL INVOICE",
                    fontsize=20,
                    color=(0.15, 0.15, 0.15),
                    fontname="helv",
                )
                if vendor:
                    page.insert_text(
                        pymupdf.Point(40, 85),
                        vendor["name"],
                        fontsize=12,
                        color=(0.3, 0.3, 0.3),
                        fontname="helv",
                    )

            # Metadata section (Invoice No, Date, Vendor address)
            y_meta = 120
            if vendor:
                page.insert_text(
                    pymupdf.Point(40, y_meta),
                    vendor["address"][:45],
                    fontsize=9,
                    color=(0.4, 0.4, 0.4),
                )
                if vendor.get("tax_id"):
                    page.insert_text(
                        pymupdf.Point(40, y_meta + 15),
                        f"Tax/VAT ID: {vendor['tax_id']}",
                        fontsize=9,
                        color=(0.4, 0.4, 0.4),
                    )

            # Invoice Number & Date Box
            if invoice_number:
                page.insert_text(
                    pymupdf.Point(360, y_meta),
                    f"Invoice #: {invoice_number}",
                    fontsize=11,
                    fontname="helv",
                )
            else:
                page.insert_text(
                    pymupdf.Point(360, y_meta),
                    "[Invoice Number: NOT SPECIFIED]",
                    fontsize=9,
                    color=(0.7, 0.2, 0.2),
                )

            # Format date representation (deliberate formatting differences)
            date_display = invoice_date
            if index == 23:
                date_display = "03/04/2024"  # Ambiguous
            elif layout == "corporate_classic":
                date_display = invoice_date  # ISO
            page.insert_text(
                pymupdf.Point(360, y_meta + 18),
                f"Date: {date_display}",
                fontsize=10,
                color=(0.2, 0.2, 0.2),
            )

            # Due Date notice (for index 25 inconsistency check)
            due_date_str = "2024-11-05" if index == 25 else "2024-12-31"
            page.insert_text(
                pymupdf.Point(360, y_meta + 34),
                f"Due Date: {due_date_str}",
                fontsize=9,
                color=(0.4, 0.4, 0.4),
            )

            # Bill To box
            page.draw_rect(
                pymupdf.Rect(40, y_meta + 55, 300, y_meta + 105),
                color=(0.8, 0.8, 0.8),
                width=0.8,
            )
            page.insert_text(
                pymupdf.Point(48, y_meta + 70), "BILL TO:", fontsize=9, fontname="helv"
            )
            page.insert_text(
                pymupdf.Point(48, y_meta + 85), customer["name"], fontsize=10, fontname="helv"
            )
            page.insert_text(
                pymupdf.Point(48, y_meta + 98),
                customer["address"],
                fontsize=8,
                color=(0.4, 0.4, 0.4),
            )

            # Line Items Table
            y_table = y_meta + 130
            page.draw_rect(
                pymupdf.Rect(40, y_table, width - 40, y_table + 22),
                color=None,
                fill=(0.92, 0.94, 0.96),
            )
            page.insert_text(
                pymupdf.Point(50, y_table + 15), "Description", fontsize=9, fontname="helv"
            )
            page.insert_text(pymupdf.Point(320, y_table + 15), "Qty", fontsize=9, fontname="helv")
            page.insert_text(
                pymupdf.Point(380, y_table + 15), "Unit Price", fontsize=9, fontname="helv"
            )
            page.insert_text(
                pymupdf.Point(480, y_table + 15), "Amount", fontsize=9, fontname="helv"
            )

            y_row = y_table + 40
            for desc, price, qty in items:
                amt = price * qty
                page.insert_text(pymupdf.Point(50, y_row), desc[:40], fontsize=9)
                page.insert_text(pymupdf.Point(325, y_row), str(qty), fontsize=9)
                page.insert_text(pymupdf.Point(385, y_row), f"{price:.2f}", fontsize=9)
                page.insert_text(pymupdf.Point(485, y_row), f"{amt:.2f}", fontsize=9)
                page.draw_line(
                    pymupdf.Point(40, y_row + 8),
                    pymupdf.Point(width - 40, y_row + 8),
                    color=(0.9, 0.9, 0.9),
                    width=0.5,
                )
                y_row += 28

            # Totals Section (on the last page)
            if p_idx == page_count - 1:
                y_tot = y_row + 20
                page.draw_rect(
                    pymupdf.Rect(320, y_tot, width - 40, y_tot + 85),
                    color=(0.85, 0.85, 0.85),
                    fill=(0.98, 0.98, 0.98),
                    width=0.8,
                )

                # Subtotal
                page.insert_text(pymupdf.Point(335, y_tot + 22), "Subtotal:", fontsize=10)
                sub_str = (
                    f"{subtotal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    if index == 27
                    else f"{subtotal:.2f}"
                )
                page.insert_text(
                    pymupdf.Point(450, y_tot + 22), f"{currency} {sub_str}", fontsize=10
                )

                # Tax
                page.insert_text(pymupdf.Point(335, y_tot + 44), "Tax / VAT:", fontsize=10)
                if tax is not None:
                    tax_str = (
                        f"{tax:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        if index == 27
                        else f"{tax:.2f}"
                    )
                    page.insert_text(
                        pymupdf.Point(450, y_tot + 44), f"{currency} {tax_str}", fontsize=10
                    )
                else:
                    page.insert_text(
                        pymupdf.Point(450, y_tot + 44),
                        "EXEMPT / 0.00",
                        fontsize=9,
                        color=(0.4, 0.4, 0.4),
                    )

                # Total
                page.draw_line(
                    pymupdf.Point(325, y_tot + 56),
                    pymupdf.Point(width - 45, y_tot + 56),
                    color=(0.8, 0.8, 0.8),
                    width=0.8,
                )
                page.insert_text(
                    pymupdf.Point(335, y_tot + 75), "TOTAL:", fontsize=11, fontname="helv"
                )
                tot_str = (
                    f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    if index == 27
                    else f"{total:.2f}"
                )
                page.insert_text(
                    pymupdf.Point(450, y_tot + 75),
                    f"{currency} {tot_str}",
                    fontsize=12,
                    fontname="helv",
                )

            # Footer
            page.insert_text(
                pymupdf.Point(40, height - 35),
                f"Page {p_idx + 1} of {page_count} | DocuMind Synthetic Invoice Corpus | Internal ID: {invoice_number or 'NONE'}",
                fontsize=8,
                color=(0.6, 0.6, 0.6),
            )

        return doc

    def _convert_to_scanned_pdf(
        self,
        digital_doc: pymupdf.Document,
        characteristics: DocumentCharacteristics,
    ) -> pymupdf.Document:
        """Convert digital PDF into image-only scanned PDF without native text layer."""
        scanned_doc = pymupdf.open()
        dpi = characteristics.resolution_dpi
        rotation = characteristics.rotation_degrees
        quality = characteristics.jpeg_quality or 75
        contrast = characteristics.contrast_factor

        for page in digital_doc:
            # Render page to raster pixmap
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            # Apply rotation / skew simulation
            if abs(rotation) > 0.01:
                img = img.rotate(
                    rotation,
                    resample=Image.Resampling.BICUBIC,
                    expand=False,
                    fillcolor=(255, 255, 255),
                )

            # Apply contrast adjustments
            if abs(contrast - 1.0) > 0.01:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(contrast)

            # Save as JPEG with compression artifacts
            jpeg_buf = io.BytesIO()
            img.save(jpeg_buf, format="JPEG", quality=quality, optimize=True)
            jpeg_bytes = jpeg_buf.getvalue()

            # Create clean page with identical point dimensions
            scanned_page = scanned_doc.new_page(width=page.rect.width, height=page.rect.height)
            # Insert the image across the full page canvas
            scanned_page.insert_image(page.rect, stream=jpeg_bytes)

        return scanned_doc


def generate_dataset(seed: int = 42) -> DatasetManifest:
    """Convenience entry point for generating the complete synthetic dataset."""
    generator = SyntheticInvoiceGenerator(seed=seed)
    return generator.generate_corpus()
