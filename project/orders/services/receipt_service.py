"""
orders/services/receipt_service.py

Purpose:
Build receipt data and PDF output for completed orders.

Responsibilities:
- validate that the order belongs to the requesting user
- ensure only completed orders can have receipts
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

from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


User = get_user_model()



def _format_money(value: Decimal | None) -> str:
    if value is None:
        return "0.00"
    return f"{value:.2f}"


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

    return "\n".join(
        part
        for part in [
            address.get("line_1"),
            address.get("line_2"),
            address.get("city"),
            address.get("postcode"),
        ]
        if part
    ) or "Not provided"


def _build_receipt_items(order: Order) -> list[dict]:
    items_payload: list[dict] = []

    for item in order.items.all():
        unit_discount = max(
            Decimal("0.00"),
            item.original_unit_price - item.final_unit_price,
        )
        line_subtotal = item.original_unit_price * item.quantity
        line_discount = unit_discount * item.quantity
        line_vat = item.vat_amount * item.quantity
        line_total = item.final_unit_price * item.quantity

        items_payload.append(
            {
                "id": item.id,
                "product_name": _get_product_name(item),
                "producer_name": _get_producer_name_from_item(item),
                "quantity": item.quantity,
                "unit_price": item.original_unit_price,
                "discount_amount": unit_discount,
                "vat_amount": item.vat_amount,
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

    if order.status != Order.Status.COMPLETED:
        raise ValidationError("Receipt is only available for completed orders.")

    items = _build_receipt_items(order)
    producer_breakdown = _build_producer_breakdown(order)

    subtotal = sum(item["line_subtotal"] for item in items)
    discount = sum(item["line_discount"] for item in items)
    vat = sum(item["line_vat"] for item in items)
    final_total = sum(item["line_total"] for item in items)

    return {
        "id": order.id,
        "order_number": order.unique_reference,
        "order_date": timezone.localtime(order.order_date),
        "status": order.get_status_display(),
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


def _wrap_text(text: str, font_name: str, font_size: int, max_width: float) -> list[str]:
    """
    Simple manual text wrapper for thermal receipt layout.
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


def _draw_wrapped_line(c, text, x, y, width, font_name="Courier", font_size=9, leading=11):
    lines = _wrap_text(text, font_name, font_size, width)
    c.setFont(font_name, font_size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def _draw_key_value(c, key, value, x, y, width, key_font="Courier-Bold", value_font="Courier", font_size=9):
    c.setFont(key_font, font_size)
    c.drawString(x, y, key)

    value_y = y - 11
    value_y = _draw_wrapped_line(
        c,
        value,
        x,
        value_y,
        width,
        font_name=value_font,
        font_size=font_size,
        leading=11,
    )
    return value_y - 4


def _draw_separator(c, x1, x2, y):
    c.setLineWidth(0.6)
    c.line(x1, y, x2, y)
    return y - 8


def _draw_center_text(c, text, page_width, y, font_name="Courier-Bold", font_size=10):
    c.setFont(font_name, font_size)
    text_width = stringWidth(text, font_name, font_size)
    c.drawString((page_width - text_width) / 2, y, text)
    return y - 12


def build_receipt_pdf(*, user: User, order_id: int):
    """
    Thermal receipt style PDF:
    - narrow receipt width
    - monospace font
    - simple, professional, print-like layout
    """
    receipt = get_receipt_data(user=user, order_id=order_id)
    order = get_order_detail_for_user(user=user, order_id=order_id)

    buffer = BytesIO()

    # Thermal receipt style width
    page_width = 80 * mm
    page_height = 297 * mm  # tall page; enough space for long receipts

    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    left = 6 * mm
    right = page_width - 6 * mm
    content_width = right - left
    y = page_height - 10 * mm

    # ===== BRANDING =====
    y = _draw_center_text(
        c,
        "BRISTOL REGIONAL FOOD NETWORK",
        page_width,
        y,
        font_name="Courier-Bold",
        font_size=10,
    )
    y = _draw_center_text(
        c,
        "ORDER RECEIPT",
        page_width,
        y,
        font_name="Courier-Bold",
        font_size=9,
    )
    y = _draw_separator(c, left, right, y)

    # ===== SUMMARY =====
    c.setFont("Courier-Bold", 9)
    c.drawString(left, y, "RECEIPT SUMMARY")
    y -= 12

    y = _draw_key_value(c, "Order Number", receipt["order_number"], left, y, content_width)
    y = _draw_key_value(
        c,
        "Order Date",
        receipt["order_date"].strftime("%d %b %Y, %H:%M"),
        left,
        y,
        content_width,
    )
    y = _draw_key_value(c, "Customer", receipt["customer_name"], left, y, content_width)
    y = _draw_key_value(
        c,
        "Payment",
        receipt["payment_method_display"] or "Not available",
        left,
        y,
        content_width,
    )

    y = _draw_separator(c, left, right, y)

    # ===== ITEMS =====
    c.setFont("Courier-Bold", 9)
    c.drawString(left, y, "ITEMS")
    y -= 12

    for item in receipt["items"]:
        unit_discount = item["discount_amount"]
        total_saved = item["line_discount"]

        c.setFont("Courier-Bold", 9)
        c.drawString(left, y, _safe_text(item["product_name"]))
        y -= 11

        c.setFont("Courier", 9)
        producer_lines = _wrap_text(
            f"Producer: {_safe_text(item['producer_name'])}",
            "Courier",
            9,
            content_width,
        )
        for line in producer_lines:
            c.drawString(left, y, line)
            y -= 10

        c.drawString(left, y, f"Quantity: {_safe_text(item['quantity'])}")
        y -= 10
        c.drawString(left, y, f"Original Unit Price: {_money(item['unit_price'])}")
        y -= 10
        c.drawString(left, y, f"Per Unit Discount: {_money(unit_discount)} each")
        y -= 10
        c.drawString(left, y, f"Total Saved: {_money(total_saved)}")
        y -= 10
        c.drawString(left, y, f"VAT: {_money(item['vat_amount'])}")
        y -= 10
        c.drawString(left, y, f"Paid Unit Price: {_money(item['final_unit_price'])}")
        y -= 10
        c.drawString(left, y, f"Line Total: {_money(item['line_total'])}")
        y -= 12

        y = _draw_separator(c, left, right, y)

    # ===== FULFILMENT DETAILS =====
    c.setFont("Courier-Bold", 9)
    c.drawString(left, y, "FULFILMENT DETAILS")
    y -= 12

    for producer in receipt["producer_breakdown"]:
        c.setFont("Courier-Bold", 9)
        producer_name_lines = _wrap_text(
            _safe_text(producer["producer_name"]),
            "Courier-Bold",
            9,
            content_width,
        )
        for line in producer_name_lines:
            c.drawString(left, y, line)
            y -= 10

        c.setFont("Courier", 9)
        fulfilment_type = _safe_text(producer["delivery_or_collection"])
        c.drawString(left, y, fulfilment_type)
        y -= 10

        if producer["delivery_date"]:
            c.drawString(left, y, f"Date: {_format_date(producer['delivery_date'])}")
            y -= 10

        if producer["collection_date"]:
            c.drawString(left, y, f"Date: {_format_date(producer['collection_date'])}")
            y -= 10

        if producer["delivery_time_slot"]:
            c.drawString(left, y, f"Time Slot: {_safe_text(producer['delivery_time_slot'])}")
            y -= 10

        if producer["collection_time_slot"]:
            c.drawString(left, y, f"Time Slot: {_safe_text(producer['collection_time_slot'])}")
            y -= 10

        if producer["delivery_address"]:
            c.setFont("Courier-Bold", 9)
            c.drawString(left, y, "Delivery Address")
            y -= 10
            c.setFont("Courier", 9)
            address_text = _format_address(producer["delivery_address"])

            for raw_line in address_text.split("\n"):
                wrapped_lines = _wrap_text(raw_line, "Courier", 9, content_width)
                for line in wrapped_lines:
                    c.drawString(left, y, line)
                    y -= 10

        if producer["collection_address"]:
            c.setFont("Courier-Bold", 9)
            c.drawString(left, y, "Collection Address")
            y -= 10
        
            c.setFont("Courier", 9)
        
            address_text = _format_address(producer["collection_address"])
        
            for raw_line in address_text.split("\n"):
                wrapped_lines = _wrap_text(raw_line, "Courier", 9, content_width)
                for line in wrapped_lines:
                    c.drawString(left, y, line)
                    y -= 10

        c.setFont("Courier-Bold", 9)
        c.drawString(left, y, "Special Instructions")
        y -= 10
        c.setFont("Courier", 9)
        instruction_lines = _wrap_text(
            _safe_text(producer["special_instructions"]),
            "Courier",
            9,
            content_width,
        )
        for line in instruction_lines:
            c.drawString(left, y, line)
            y -= 10

        y = _draw_separator(c, left, right, y)

    # ===== TOTALS =====
    c.setFont("Courier-Bold", 9)
    c.drawString(left, y, "TOTALS")
    y -= 12

    totals = receipt["totals"]

    c.setFont("Courier", 9)
    c.drawString(left, y, "Subtotal")
    c.drawRightString(right, y, _money(totals["subtotal"]))
    y -= 10

    c.drawString(left, y, "Discount")
    c.drawRightString(right, y, _money(totals["discount"]))
    y -= 10

    c.drawString(left, y, "VAT")
    c.drawRightString(right, y, _money(totals["vat"]))
    y -= 10

    c.setFont("Courier-Bold", 9)
    c.drawString(left, y, "Final Total")
    c.drawRightString(right, y, _money(totals["final_total"]))
    y -= 12

    y = _draw_separator(c, left, right, y)

    # ===== FOOTER =====
    y = _draw_center_text(
        c,
        "Thank you for your order",
        page_width,
        y,
        font_name="Courier",
        font_size=9,
    )
    y = _draw_center_text(
        c,
        "Keep this receipt for support or collection",
        page_width,
        y,
        font_name="Courier",
        font_size=8,
    )

    c.save()
    buffer.seek(0)
    return order, buffer