"""Table line-item extraction using spatial column boundaries and row clustering.

Extracts line-item descriptions, quantities, unit prices, and row amounts from
invoice tables across single-page and multi-page documents without external LLMs.
"""

import re
from decimal import Decimal

from documind.extraction.money_parser import parse_monetary_value
from documind.extraction.patterns import (
    TABLE_HEADER_AMOUNT,
    TABLE_HEADER_DESCRIPTION,
    TABLE_HEADER_QTY,
    TABLE_HEADER_UNIT_PRICE,
)
from documind.extraction.spatial import (
    SpatialLine,
    cluster_words_into_lines,
    get_words_ocr_confidence,
    merge_bounding_boxes,
)
from documind.schemas.invoice import InvoiceLineItem


class LineItemExtractor:
    """Extracts structured line items from spatial document pages."""

    def extract_line_items_from_lines(
        self,
        lines: list[SpatialLine],
        page_number: int,
    ) -> list[InvoiceLineItem]:
        """Extract line items from a sequence of sorted spatial lines on a page."""
        items: list[InvoiceLineItem] = []

        # 1. Locate table header line
        header_idx: int | None = None
        for i, line in enumerate(lines):
            l_lower = line.text.lower()
            has_desc = any(h in l_lower for h in TABLE_HEADER_DESCRIPTION)
            has_qty = any(h in l_lower for h in TABLE_HEADER_QTY)
            has_price = any(h in l_lower for h in TABLE_HEADER_UNIT_PRICE)
            has_amt = any(h in l_lower for h in TABLE_HEADER_AMOUNT)

            if has_desc and (has_qty or has_price or has_amt):
                header_idx = i
                break

        if header_idx is None:
            return []

        header_line = lines[header_idx]

        # 2. Determine column boundaries based on header word locations
        x_qty = 320.0
        x_price = 380.0
        x_amt = 480.0

        for w in header_line.words:
            w_low = w.text.lower()
            if any(h in w_low for h in TABLE_HEADER_QTY):
                x_qty = w.bounding_box.x0
            elif any(h in w_low for h in TABLE_HEADER_UNIT_PRICE):
                x_price = w.bounding_box.x0
            elif any(h in w_low for h in TABLE_HEADER_AMOUNT):
                x_amt = w.bounding_box.x0

        col_qty_left = x_qty - 20.0
        col_price_left = x_price - 20.0
        col_amt_left = x_amt - 20.0

        # 3. Iterate rows below header
        for i in range(header_idx + 1, len(lines)):
            line = lines[i]
            l_lower = line.text.lower()

            # Stop when reaching totals or footer section
            if any(
                k in l_lower
                for k in ["subtotal", "tax / vat", "tax/vat", "total:", "gross total", "page "]
            ):
                break

            # Stop if vertical position is well into footer/totals zone (> 650pt on standard A4)
            if line.y_center > 650.0:
                break

            # Partition words by horizontal column
            desc_words = []
            qty_words = []
            price_words = []
            amt_words = []

            for w in line.words:
                mid_x = (w.bounding_box.x0 + w.bounding_box.x1) / 2.0
                if mid_x < col_qty_left:
                    desc_words.append(w)
                elif mid_x < col_price_left:
                    qty_words.append(w)
                elif mid_x < col_amt_left:
                    price_words.append(w)
                else:
                    amt_words.append(w)

            desc_text = " ".join(w.text for w in desc_words).strip()
            qty_text = " ".join(w.text for w in qty_words).strip()
            price_text = " ".join(w.text for w in price_words).strip()
            amt_text = " ".join(w.text for w in amt_words).strip()

            # Parse numeric values
            quantity: Decimal | None = None
            if qty_text:
                qty_clean = re.sub(r"[^\d.]", "", qty_text)
                if qty_clean:
                    try:
                        quantity = Decimal(qty_clean)
                    except Exception:
                        quantity = None

            unit_price: Decimal | None = None
            if price_text:
                res_price = parse_monetary_value(price_text)
                if res_price.is_valid:
                    unit_price = res_price.amount

            total: Decimal | None = None
            if amt_text:
                res_amt = parse_monetary_value(amt_text)
                if res_amt.is_valid:
                    total = res_amt.amount

            # Accept row if description exists and at least one financial/qty element is present
            if desc_text and (quantity is not None or unit_price is not None or total is not None):
                bbox = merge_bounding_boxes(line.words, page_number)
                ocr_conf = get_words_ocr_confidence(line.words)
                items.append(
                    InvoiceLineItem(
                        description=desc_text,
                        quantity=quantity,
                        unit_of_measure=None,
                        unit_price=unit_price,
                        discount=None,
                        tax=None,
                        total=total,
                        raw_text=line.text,
                        bounding_box=bbox,
                        page_number=page_number,
                        confidence=ocr_conf if ocr_conf is not None else 1.0,
                        status="extracted",
                    )
                )

        return items

    def extract_line_items_from_pages(
        self,
        pages: list,
    ) -> list[InvoiceLineItem]:
        """Extract line items across all pages in a document."""
        all_items: list[InvoiceLineItem] = []
        for p in pages:
            words = [w for b in p.text_blocks for w in b.words]
            lines = cluster_words_into_lines(words)
            page_items = self.extract_line_items_from_lines(lines, p.page_number)
            all_items.extend(page_items)
        return all_items
