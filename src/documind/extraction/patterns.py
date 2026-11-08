"""Keyword definitions and regex patterns for invoice field extraction.

Defines standard lexical markers, contextual headers, and regular expressions
for invoice identifiers, dates, financial summaries, vendor information, and tables.
"""

import re

# Invoice Identification Labels
INVOICE_NUMBER_LABELS = [
    "invoice #:",
    "invoice #",
    "invoice no.:",
    "invoice no:",
    "invoice no",
    "invoice number:",
    "invoice number",
    "inv #:",
    "inv #",
    "inv no:",
    "bill no:",
    "rechnung nr:",
    "rechnung nr",
]

INVOICE_DATE_LABELS = [
    "invoice date:",
    "invoice date",
    "date of issue:",
    "date of issue",
    "issue date:",
    "issue date",
    "date:",
    "dated:",
]

DUE_DATE_LABELS = [
    "due date:",
    "due date",
    "payment due:",
    "payment due",
    "due by:",
    "due:",
    "payable by:",
]

PO_NUMBER_LABELS = [
    "po #:",
    "po #",
    "purchase order:",
    "purchase order",
    "p.o. no:",
    "po number:",
    "order #:",
]

# Vendor Information Labels & Patterns
VENDOR_TAX_ID_LABELS = [
    "tax/vat id:",
    "tax/vat id",
    "tax id:",
    "tax id",
    "vat id:",
    "vat id",
    "vat reg no:",
    "ein:",
    "tax registration:",
]

# Customer Section Labels
CUSTOMER_SECTION_LABELS = [
    "bill to:",
    "bill to",
    "invoice to:",
    "invoice to",
    "sold to:",
    "sold to",
    "customer:",
    "client:",
]

# Financial Summary Labels
SUBTOTAL_LABELS = [
    "subtotal:",
    "subtotal",
    "sub-total:",
    "sub-total",
    "net total:",
    "net amount:",
]

TAX_LABELS = [
    "tax / vat:",
    "tax / vat",
    "tax/vat:",
    "tax/vat",
    "tax:",
    "tax",
    "vat:",
    "vat",
    "sales tax:",
    "taxes:",
]

TOTAL_LABELS = [
    "total:",
    "total",
    "total amount:",
    "total amount",
    "gross total:",
    "amount due:",
    "balance due:",
]

# Table Header Column Markers
TABLE_HEADER_DESCRIPTION = ["description", "item", "service", "details"]
TABLE_HEADER_QTY = ["qty", "quantity", "units", "hrs", "hours"]
TABLE_HEADER_UNIT_PRICE = ["unit price", "price", "rate", "unit cost", "unit"]
TABLE_HEADER_AMOUNT = ["amount", "line total", "total", "net amount"]

# Generic regex patterns
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
TAX_ID_PATTERN = re.compile(
    r"\b(?:[A-Z]{2}-)?(?:VAT|EIN|MVA|TAX|TIN)?-?[A-Z0-9-]{6,20}\b",
    re.IGNORECASE,
)
