"""
orders/services/receipt_service.py

Purpose:
Build receipt data and PDF output for customer orders.

Responsibilities:
- validate that the order belongs to the requesting user
- ensure only eligible customer orders can have receipts
- build a clean receipt payload for API responses
- mask card payment details
- generate a professional downloadable PDF receipt
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from orders.models import Order
from orders.selectors import get_order_detail_for_user

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from orders.services.order_status import get_order_status_context

User = get_user_model()


def _format_money(value: Decimal | None) -> str:
    if value is None:
        return "0.00"
    return f"{value:.2f}"


def _structured_validation_error(
    *,
    code: str,
    message: str,
    data: dict | None = None,
) -> ValidationError:
    return ValidationError(
        {
            "code": code,
            "message": message,
            "data": data or {},
        }
    )


def _money(value: Decimal | None) -> str:
    return f"£{_format_money(value)}"


def _mask_card(last4: str | None) -> str | None:
    if not last4:
        return None
    return f"**** **** **** {last4}"


def _get_customer_name(order: Order) -> str:
    if order.is_guest:
        return order.guest_name or "Guest customer"

    user = getattr(order, "user", None)
    if not user:
        return "Customer"

    return user.name or "Customer"


def _get_payment_method_display(order: Order) -> str | None:
    """
    Build a safe payment method display string.

    Behaviour:
    - prefers a successful payment if one exists
    - masks card payments
    - otherwise returns the payment method display text
    """
    payments = list(order.payments.all().order_by("-created_at"))

    if not payments:
        return None

    successful_payment = next(
        (
            payment
            for payment in payments
            if payment.payment_status == payment.Status.SUCCESS
        ),
        None,
    )
    payment = successful_payment or payments[0]

    if payment.payment_method == payment.Method.CARD:
        masked = _mask_card(payment.card_last4)
        if masked and payment.card_brand:
            return f"{payment.card_brand.title()} {masked}"
        if masked:
            return masked
        return "Card"

    return payment.get_payment_method_display()


def _get_product_name(item) -> str:
    snapshot_name = getattr(item, "product_name_snapshot", None)
    if snapshot_name:
        return snapshot_name

    if item.product_id and item.product:
        return item.product.name

    return "Unknown product"


def _get_producer_name_from_item(item) -> str:
    snapshot_name = getattr(item, "producer_name_snapshot", None)
    if snapshot_name:
        return snapshot_name

    if item.producer_id and item.producer:
        farm_name = getattr(item.producer, "farm_name", None)
        if farm_name:
            return farm_name
        return str(item.producer)

    return "Unknown producer"


def _get_producer_name_from_summary(summary) -> str:
    if summary.producer_id and summary.producer:
        farm_name = getattr(summary.producer, "farm_name", None)
        if farm_name:
            return farm_name
        return str(summary.producer)

    return "Unknown producer"


def _build_address_payload(summary) -> dict | None:
    if not any(
        [
            summary.address_line1,
            summary.address_line2,
            summary.city,
            summary.postcode,
        ]
    ):
        return None

    return {
        "line_1": summary.address_line1,
        "line_2": summary.address_line2,
        "city": summary.city,
        "postcode": summary.postcode,
    }


def _format_address(address: dict | None) -> str:
    if not address:
        return "Not provided"

    return (
        "\n".join(
            part
            for part in [
                address.get("line_1"),
                address.get("line_2"),
                address.get("city"),
                address.get("postcode"),
            ]
            if part
        )
        or "Not provided"
    )


def _active_quantity(item) -> int:
    return max(item.quantity - getattr(item, "cancelled_quantity", 0), 0)


def _vat_per_unit(item) -> Decimal:
    if item.quantity <= 0:
        return Decimal("0.00")

    return Decimal(item.vat_amount or 0) / Decimal(item.quantity)


def _build_receipt_items(order: Order) -> list[dict]:
    items_payload: list[dict] = []

    for item in order.items.all():
        active_quantity = _active_quantity(item)
        cancelled_quantity = getattr(item, "cancelled_quantity", 0)

        if active_quantity <= 0:
            continue

        unit_discount = max(
            Decimal("0.00"),
            item.original_unit_price - item.final_unit_price,
        )

        vat_per_unit = _vat_per_unit(item)

        line_subtotal = item.original_unit_price * active_quantity
        line_discount = unit_discount * active_quantity
        line_vat = vat_per_unit * active_quantity
        line_total = item.final_unit_price * active_quantity

        items_payload.append(
            {
                "id": item.id,
                "product_name": _get_product_name(item),
                "producer_name": _get_producer_name_from_item(item),
                "quantity": active_quantity,
                "original_quantity": item.quantity,
                "cancelled_quantity": cancelled_quantity,
                "unit_price": item.original_unit_price,
                "discount_amount": unit_discount,
                "vat_amount": vat_per_unit,
                "final_unit_price": item.final_unit_price,
                "line_subtotal": line_subtotal,
                "line_discount": line_discount,
                "line_vat": line_vat,
                "line_total": line_total,
            }
        )

    return items_payload


def _build_producer_breakdown(order: Order) -> list[dict]:
    producer_payload: list[dict] = []

    for summary in order.producer_summaries.all():
        address = _build_address_payload(summary)

        producer_payload.append(
            {
                "id": summary.id,
                "producer_id": summary.producer_id,
                "producer_name": _get_producer_name_from_summary(summary),
                "status": summary.get_status_display(),
                "delivery_or_collection": summary.get_delivery_or_collection_display(),
                "delivery_date": (
                    summary.delivery_date
                    if summary.delivery_or_collection
                    == Order.DeliveryOrCollection.DELIVERY
                    else None
                ),
                "collection_date": (
                    summary.delivery_date
                    if summary.delivery_or_collection
                    == Order.DeliveryOrCollection.COLLECTION
                    else None
                ),
                "delivery_time_slot": (
                    summary.delivery_time_slot
                    if summary.delivery_or_collection
                    == Order.DeliveryOrCollection.DELIVERY
                    else None
                ),
                "collection_time_slot": (
                    summary.delivery_time_slot
                    if summary.delivery_or_collection
                    == Order.DeliveryOrCollection.COLLECTION
                    else None
                ),
                "delivery_address": (
                    address
                    if summary.delivery_or_collection
                    == Order.DeliveryOrCollection.DELIVERY
                    else None
                ),
                "collection_address": (
                    address
                    if summary.delivery_or_collection
                    == Order.DeliveryOrCollection.COLLECTION
                    else None
                ),
                "subtotal": summary.subtotal,
                "vat_total": summary.vat_total,
                "special_instructions": summary.special_instructions,
            }
        )

    return producer_payload


def get_receipt_data(*, user: User, order_id: int) -> dict:
    order = get_order_detail_for_user(user=user, order_id=order_id)
    status_context = get_order_status_context(order)

    if status_context["status_key"] == "cancelled":
        raise _structured_validation_error(
            code="receipt_not_available",
            message="Receipt is not available for cancelled orders.",
            data={
                "order_id": order.id,
                "order_status": status_context["status_key"],
            },
        )

    items = _build_receipt_items(order)
    producer_breakdown = _build_producer_breakdown(order)

    subtotal = sum(item["line_subtotal"] for item in items)
    discount = sum(item["line_discount"] for item in items)
    vat = sum(item["line_vat"] for item in items)
    final_total = sum(item["line_total"] + item["line_vat"] for item in items)

    return {
        "id": order.id,
        "order_number": order.unique_reference,
        "order_date": timezone.localtime(order.order_date),
        "status": status_context["status_display"],
        "customer_name": _get_customer_name(order),
        "payment_method_display": _get_payment_method_display(order),
        "items": items,
        "producer_breakdown": producer_breakdown,
        "totals": {
            "subtotal": subtotal,
            "discount": discount,
            "vat": vat,
            "final_total": final_total,
        },
    }

def _safe_text(value) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text if text else "-"


def _format_date(value) -> str:
    if not value:
        return "-"
    return value.strftime("%d %b %Y")


def _wrap_text(
    text: str, font_name: str, font_size: int, max_width: float
) -> list[str]:
    """
    Wrap a single line of text to fit within the given width.
    """
    text = _safe_text(text)
    words = text.split()

    if not words:
        return ["-"]

    lines = []
    current = words[0]

    for word in words[1:]:
        trial = f"{current} {word}"
        if stringWidth(trial, font_name, font_size) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def _ensure_space(c, y, needed_height, page_width, page_height, left, right):
    """
    Start a new page if there is not enough vertical space left.
    """
    bottom_margin = 16 * mm
    if y - needed_height < bottom_margin:
        c.showPage()
        c.setStrokeColor(colors.black)
        return page_height - 18 * mm
    return y


def _draw_wrapped_text_block(
    c,
    text,
    x,
    y,
    width,
    *,
    font_name="Helvetica",
    font_size=9,
    leading=11,
):
    """
    Draw text preserving manual line breaks and wrapping long lines.
    """
    c.setFont(font_name, font_size)
    text = _safe_text(text)

    for raw_line in text.split("\n"):
        wrapped = _wrap_text(raw_line, font_name, font_size, width)
        for line in wrapped:
            c.drawString(x, y, line)
            y -= leading

    return y


def _draw_label_value_inline(
    c,
    label,
    value,
    left,
    right,
    y,
    *,
    label_font="Helvetica-Bold",
    value_font="Helvetica",
    font_size=9,
):
    c.setFont(label_font, font_size)
    c.drawString(left, y, label)
    c.setFont(value_font, font_size)
    c.drawRightString(right, y, _safe_text(value))
    return y - 11


def _draw_section_title(c, title, left, right, y):
    y -= 2
    c.setLineWidth(0.8)
    c.line(left, y, right, y)
    y -= 11
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, title.upper())
    return y - 10


def _draw_receipt_header(c, page_width, left, right, y, receipt):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, "Bristol Regional Food Network")
    y -= 13

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawString(left, y, "Order Receipt")
    c.setFillColor(colors.black)
    y -= 16

    c.setLineWidth(1)
    c.line(left, y, right, y)
    y -= 14

    col_gap = 12 * mm
    col_width = ((right - left) - col_gap) / 2
    left_col_x = left
    right_col_x = left + col_width + col_gap

    top_y = y

    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_col_x, y, "Order Number")
    y -= 11
    y = _draw_wrapped_text_block(
        c,
        receipt["order_number"],
        left_col_x,
        y,
        col_width,
        font_name="Helvetica",
        font_size=9,
        leading=11,
    )
    y -= 2

    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_col_x, y, "Order Date")
    y -= 11
    y = _draw_wrapped_text_block(
        c,
        receipt["order_date"].strftime("%d %b %Y, %H:%M"),
        left_col_x,
        y,
        col_width,
        font_name="Helvetica",
        font_size=9,
        leading=11,
    )

    y_right = top_y

    c.setFont("Helvetica-Bold", 9)
    c.drawString(right_col_x, y_right, "Customer")
    y_right -= 11
    y_right = _draw_wrapped_text_block(
        c,
        receipt["customer_name"],
        right_col_x,
        y_right,
        col_width,
        font_name="Helvetica",
        font_size=9,
        leading=11,
    )
    y_right -= 2

    c.setFont("Helvetica-Bold", 9)
    c.drawString(right_col_x, y_right, "Payment")
    y_right -= 11
    y_right = _draw_wrapped_text_block(
        c,
        receipt["payment_method_display"] or "Not available",
        right_col_x,
        y_right,
        col_width,
        font_name="Helvetica",
        font_size=9,
        leading=11,
    )

    y = min(y, y_right) - 10
    return y


def build_receipt_pdf(*, user: User, order_id: int):
    receipt = get_receipt_data(user=user, order_id=order_id)
    order = get_order_detail_for_user(user=user, order_id=order_id)

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Receipt {receipt['order_number']}",
    )

    styles = getSampleStyleSheet()

    brand_style = ParagraphStyle(
        "Brand",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=2,
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#555555"),
        spaceAfter=10,
    )

    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        textColor=colors.black,
        spaceBefore=6,
        spaceAfter=6,
    )

    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.black,
    )

    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.black,
    )

    small_muted_style = ParagraphStyle(
        "SmallMuted",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#666666"),
    )

    total_style = ParagraphStyle(
        "Total",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=TA_RIGHT,
    )

    story = []

    # Header
    story.append(Paragraph("Bristol Regional Food Network", brand_style))
    story.append(Paragraph("Order Receipt", subtitle_style))

    # Summary
    story.append(Paragraph("Receipt Summary", section_style))

    summary_data = [
        [
            Paragraph(
                "<b>Order Number</b><br/>" + receipt["order_number"], value_style
            ),
            Paragraph(
                "<b>Order Date</b><br/>"
                + receipt["order_date"].strftime("%d %b %Y, %H:%M"),
                value_style,
            ),
        ],
        [
            Paragraph(
                "<b>Customer</b><br/>" + _safe_text(receipt["customer_name"]),
                value_style,
            ),
            Paragraph(
                "<b>Payment</b><br/>"
                + _safe_text(receipt["payment_method_display"] or "Not available"),
                value_style,
            ),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[89 * mm, 89 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9D9D9")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E5E5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Items
    story.append(Paragraph("Items", section_style))

    item_rows = [
        [
            Paragraph("<b>Product</b>", small_muted_style),
            Paragraph("<b>Producer</b>", small_muted_style),
            Paragraph("<b>Quantity</b>", small_muted_style),
            Paragraph("<b>Original</b>", small_muted_style),
            Paragraph("<b>Discount Per unit</b>", small_muted_style),
            Paragraph("<b>VAT</b>", small_muted_style),
            Paragraph("<b>Paid</b>", small_muted_style),
            Paragraph("<b>Total</b>", small_muted_style),
        ]
    ]

    for item in receipt["items"]:
        item_rows.append(
            [
                Paragraph(_safe_text(item["product_name"]), value_style),
                Paragraph(_safe_text(item["producer_name"]), value_style),
                Paragraph(str(item["quantity"]), value_style),
                Paragraph(_money(item["unit_price"]), value_style),
                Paragraph(_money(item["discount_amount"]), value_style),
                Paragraph(_money(item["vat_amount"]), value_style),
                Paragraph(_money(item["final_unit_price"]), value_style),
                Paragraph(_money(item["line_total"]), value_style),
            ]
        )

        if item["line_discount"] and item["line_discount"] > 0:
            item_rows.append(
                [
                    Paragraph(
                        f"Saved {_money(item['line_discount'])} total",
                        small_muted_style,
                    ),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

    items_table = Table(
        item_rows,
        colWidths=[
            34 * mm,
            28 * mm,
            16 * mm,
            20 * mm,
            20 * mm,
            16 * mm,
            20 * mm,
            20 * mm,
        ],
        repeatRows=1,
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#CFCFCF")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#E5E5E5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("SPAN", (0, 2), (-1, 2)),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 10))

    # Fulfilment
    story.append(Paragraph("Fulfilment Details", section_style))

    for producer in receipt["producer_breakdown"]:
        detail_rows = [
            [Paragraph(f"<b>{_safe_text(producer['producer_name'])}</b>", value_style)],
            [
                Paragraph(
                    _safe_text(producer["delivery_or_collection"]), small_muted_style
                )
            ],
        ]

        if producer["delivery_date"]:
            detail_rows.append(
                [
                    Paragraph(
                        f"<b>Date</b><br/>{_format_date(producer['delivery_date'])}",
                        value_style,
                    )
                ]
            )
        if producer["collection_date"]:
            detail_rows.append(
                [
                    Paragraph(
                        f"<b>Date</b><br/>{_format_date(producer['collection_date'])}",
                        value_style,
                    )
                ]
            )
        if producer["delivery_time_slot"]:
            detail_rows.append(
                [
                    Paragraph(
                        f"<b>Time Slot</b><br/>{_safe_text(producer['delivery_time_slot'])}",
                        value_style,
                    )
                ]
            )
        if producer["collection_time_slot"]:
            detail_rows.append(
                [
                    Paragraph(
                        f"<b>Time Slot</b><br/>{_safe_text(producer['collection_time_slot'])}",
                        value_style,
                    )
                ]
            )

        if producer["delivery_address"]:
            detail_rows.append(
                [
                    Paragraph(
                        "<b>Delivery Address</b><br/>"
                        + _safe_text(
                            _format_address(producer["delivery_address"])
                        ).replace("\n", "<br/>"),
                        value_style,
                    )
                ]
            )

        if producer["collection_address"]:
            detail_rows.append(
                [
                    Paragraph(
                        "<b>Collection Address</b><br/>"
                        + _safe_text(
                            _format_address(producer["collection_address"])
                        ).replace("\n", "<br/>"),
                        value_style,
                    )
                ]
            )

        detail_rows.append(
            [
                Paragraph(
                    "<b>Special Instructions</b><br/>"
                    + _safe_text(producer["special_instructions"]),
                    value_style,
                )
            ]
        )

        card = Table(detail_rows, colWidths=[178 * mm])
        card.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9D9D9")),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#ECECEC")),
                ]
            )
        )
        story.append(card)
        story.append(Spacer(1, 8))

    # Totals
    story.append(Paragraph("Totals", section_style))

    totals_rows = [
        [
            Paragraph("Subtotal", value_style),
            Paragraph(_money(receipt["totals"]["subtotal"]), value_style),
        ],
        [
            Paragraph("Discount", value_style),
            Paragraph(_money(receipt["totals"]["discount"]), value_style),
        ],
        [
            Paragraph("VAT", value_style),
            Paragraph(_money(receipt["totals"]["vat"]), value_style),
        ],
        [
            Paragraph("<b>Final Total</b>", label_style),
            Paragraph(_money(receipt["totals"]["final_total"]), total_style),
        ],
    ]

    totals_table = Table(totals_rows, colWidths=[120 * mm, 58 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9D9D9")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#ECECEC")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#FAFAFA")),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 10))

    # Footer
    story.append(Paragraph("Thank you for your order.", small_muted_style))
    story.append(
        Paragraph(
            "Keep this receipt for support, delivery, or collection reference.",
            small_muted_style,
        )
    )

    doc.build(story)
    buffer.seek(0)
    return order, buffer
