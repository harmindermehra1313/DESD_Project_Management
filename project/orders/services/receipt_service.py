"""
orders/services/receipt_service.py

Purpose:
Build receipt data and PDF output for completed orders.

Responsibilities:
- validate that the order belongs to the requesting user
- ensure only completed orders can have receipts
- build a clean receipt payload for API responses
- mask card payment details
- generate a downloadable PDF for the receipt
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from orders.models import Order
from orders.selectors import get_order_detail_for_user
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

User = get_user_model()


def _format_money(value: Decimal | None) -> str:
    """
    Format a decimal monetary value to two decimal places as a string.

    Args:
        value:
            Decimal monetary value.

    Returns:
        str:
            Money string in 0.00 format.
    """
    if value is None:
        return "0.00"
    return f"{value:.2f}"


def _mask_card(last4: str | None) -> str | None:
    """
    Mask a card number using only the last 4 digits.

    Args:
        last4:
            Stored last four digits of the card, if available.

    Returns:
        str | None:
            Masked card string or None if unavailable.
    """
    if not last4:
        return None
    return f"**** **** **** {last4}"


def _get_customer_name(order: Order) -> str:
    """
    Resolve a display-friendly customer name for the receipt.

    Only exposes name (privacy-safe).
    """
    if order.is_guest:
        return order.guest_name or "Guest customer"

    user = getattr(order, "user", None)
    if not user:
        return "Customer"

    return user.name or "Customer"


def _get_payment_method_display(order: Order) -> str | None:
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
        return "Card"

    return payment.get_payment_method_display()


def _get_product_name(item) -> str:
    """
    Resolve a display-friendly product name from snapshot or relation.

    Args:
        item:
            OrderItem instance.

    Returns:
        str:
            Product display name.
    """
    snapshot_name = getattr(item, "product_name_snapshot", None)
    if snapshot_name:
        return snapshot_name

    if item.product_id and item.product:
        return item.product.name

    return "Unknown product"


def _get_producer_name_from_item(item) -> str:
    """
    Resolve a display-friendly producer name from snapshot or relation.

    Args:
        item:
            OrderItem instance.

    Returns:
        str:
            Producer display name.
    """
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
    """
    Resolve a display-friendly producer name from ProducerOrderSummary.

    Args:
        summary:
            ProducerOrderSummary instance.

    Returns:
        str:
            Producer display name.
    """
    if summary.producer_id and summary.producer:
        farm_name = getattr(summary.producer, "farm_name", None)
        if farm_name:
            return farm_name
        return str(summary.producer)

    return "Unknown producer"


def _build_address_payload(summary) -> dict | None:
    """
    Build address payload from producer summary.

    Args:
        summary:
            ProducerOrderSummary instance.

    Returns:
        dict | None:
            Address dict or None if empty.
    """
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


def _build_receipt_items(order: Order) -> list[dict]:
    """
    Build receipt line items.

    Args:
        order:
            Order instance.

    Returns:
        list[dict]:
            Receipt line item payloads.
    """
    items_payload: list[dict] = []

    for item in order.items.all():
        line_subtotal = item.original_unit_price * item.quantity
        line_discount = item.discount_amount * item.quantity
        line_vat = item.vat_amount * item.quantity
        line_total = item.final_unit_price * item.quantity

        items_payload.append(
            {
                "id": item.id,
                "product_name": _get_product_name(item),
                "producer_name": _get_producer_name_from_item(item),
                "quantity": item.quantity,
                "unit_price": item.original_unit_price,
                "discount_amount": item.discount_amount,
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
    """
    Build receipt producer fulfilment breakdown.

    Args:
        order:
            Order instance.

    Returns:
        list[dict]:
            Producer summary payloads.
    """
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
                    if summary.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY
                    else None
                ),
                "collection_date": (
                    summary.delivery_date
                    if summary.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION
                    else None
                ),
                "delivery_time_slot": (
                    summary.delivery_time_slot
                    if summary.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY
                    else None
                ),
                "collection_time_slot": (
                    summary.delivery_time_slot
                    if summary.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION
                    else None
                ),
                "delivery_address": (
                    address
                    if summary.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY
                    else None
                ),
                "collection_address": (
                    address
                    if summary.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION
                    else None
                ),
                "subtotal": summary.subtotal,
                "vat_total": summary.vat_total,
                "special_instructions": summary.special_instructions,
            }
        )

    return producer_payload


def get_receipt_data(*, user: User, order_id: int) -> dict:
    """
    Build the receipt payload for a completed order.

    Rules:
    - the order must belong to the authenticated user
    - only completed orders can have receipts

    Args:
        user:
            Authenticated user requesting the receipt.
        order_id:
            Order primary key.

    Returns:
        dict:
            Receipt payload ready for serializer/output.

    Raises:
        ValidationError:
            If the order is not completed.
    """
    order = get_order_detail_for_user(user=user, order_id=order_id)

    if order.status != Order.Status.COMPLETED:
        raise ValidationError("Receipt is only available for completed orders.")

    return {
        "id": order.id,
        "order_number": order.unique_reference,
        "order_date": timezone.localtime(order.order_date),
        "status": order.get_status_display(),
        "customer_name": _get_customer_name(order),
        "payment_method_display": _get_payment_method_display(order),
        "items": _build_receipt_items(order),
        "producer_breakdown": _build_producer_breakdown(order),
        "totals": {
            "subtotal": order.total_price,
            "discount": order.total_discount,
            "vat": order.total_vat,
            "final_total": order.final_total_price,
        },
    }


def _draw_wrapped_lines(pdf, text: str, *, x: int, y: int, max_width: int, line_height: int) -> int:
    """
    Draw text with naive wrapping for PDF rendering.

    Args:
        pdf:
            ReportLab canvas.
        text:
            Text to render.
        x:
            X position.
        y:
            Starting Y position.
        max_width:
            Maximum width in points before wrapping.
        line_height:
            Vertical line spacing.

    Returns:
        int:
            Updated Y position after drawing.
    """
    words = (text or "").split()
    if not words:
        return y

    current_line = words[0]

    for word in words[1:]:
        test_line = f"{current_line} {word}"
        if pdf.stringWidth(test_line, "Helvetica", 10) <= max_width:
            current_line = test_line
        else:
            pdf.drawString(x, y, current_line)
            y -= line_height
            current_line = word

    pdf.drawString(x, y, current_line)
    y -= line_height
    return y


def build_receipt_pdf(*, user: User, order_id: int) -> tuple[Order, BytesIO]:
    """
    Generate a downloadable receipt PDF for a completed order.

    Args:
        user:
            Authenticated user requesting the receipt.
        order_id:
            Order primary key.

    Returns:
        tuple[Order, BytesIO]:
            The order and an in-memory PDF buffer.
    """
   

    order = get_order_detail_for_user(user=user, order_id=order_id)

    if order.status != Order.Status.COMPLETED:
        raise ValidationError("Receipt is only available for completed orders.")

    receipt = get_receipt_data(user=user, order_id=order_id)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    left = 50
    right = page_width - 50
    y = page_height - 50
    line_gap = 16

    def ensure_space(required_height: int = 80):
        nonlocal y
        if y < required_height:
            pdf.showPage()
            y = page_height - 50
            pdf.setFont("Helvetica", 10)

    pdf.setTitle(f"Receipt {receipt['order_number']}")

    # Header
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left, y, "Receipt")
    y -= 28

    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y, f"Order number: {receipt['order_number']}")
    y -= line_gap
    pdf.drawString(left, y, f"Order date: {receipt['order_date'].strftime('%d %B %Y %H:%M')}")
    y -= line_gap
    pdf.drawString(left, y, f"Status: {receipt['status']}")
    y -= line_gap
    pdf.drawString(left, y, f"Customer: {receipt['customer_name']}")
    y -= line_gap

    payment_method = receipt["payment_method_display"] or "Not available"
    pdf.drawString(left, y, f"Payment: {payment_method}")
    y -= 24

    # Items
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(left, y, "Items")
    y -= 18

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left, y, "Product")
    pdf.drawString(280, y, "Qty")
    pdf.drawString(320, y, "Unit")
    pdf.drawString(390, y, "Total")
    y -= 12

    pdf.line(left, y, right, y)
    y -= 16

    pdf.setFont("Helvetica", 10)
    for item in receipt["items"]:
        ensure_space(120)

        product_line = f"{item['product_name']} ({item['producer_name']})"
        y = _draw_wrapped_lines(
            pdf,
            product_line,
            x=left,
            y=y,
            max_width=210,
            line_height=12,
        )

        row_y = y + 12
        pdf.drawString(280, row_y, str(item["quantity"]))
        pdf.drawRightString(370, row_y, _format_money(item["final_unit_price"]))
        pdf.drawRightString(460, row_y, _format_money(item["line_total"]))
        y -= 4

    y -= 10

    # Fulfilment
    ensure_space(160)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(left, y, "Fulfilment details")
    y -= 18

    pdf.setFont("Helvetica", 10)
    for summary in receipt["producer_breakdown"]:
        ensure_space(140)

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(left, y, summary["producer_name"])
        y -= line_gap

        pdf.setFont("Helvetica", 10)
        pdf.drawString(left, y, f"Type: {summary['delivery_or_collection']}")
        y -= line_gap

        if summary["delivery_date"]:
            pdf.drawString(left, y, f"Delivery date: {summary['delivery_date'].strftime('%d %B %Y')}")
            y -= line_gap

        if summary["collection_date"]:
            pdf.drawString(left, y, f"Collection date: {summary['collection_date'].strftime('%d %B %Y')}")
            y -= line_gap

        if summary["delivery_time_slot"]:
            pdf.drawString(left, y, f"Delivery time slot: {summary['delivery_time_slot']}")
            y -= line_gap

        if summary["collection_time_slot"]:
            pdf.drawString(left, y, f"Collection time slot: {summary['collection_time_slot']}")
            y -= line_gap

        address = summary["delivery_address"] or summary["collection_address"]
        if address:
            address_text = ", ".join(
                part for part in [
                    address.get("line_1"),
                    address.get("line_2"),
                    address.get("city"),
                    address.get("postcode"),
                ]
                if part
            )
            y = _draw_wrapped_lines(
                pdf,
                f"Address: {address_text}",
                x=left,
                y=y,
                max_width=410,
                line_height=12,
            )

        if summary["special_instructions"]:
            y = _draw_wrapped_lines(
                pdf,
                f"Instructions: {summary['special_instructions']}",
                x=left,
                y=y,
                max_width=410,
                line_height=12,
            )

        y -= 8

    # Totals
    ensure_space(120)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(left, y, "Totals")
    y -= 20

    totals = receipt["totals"]

    pdf.setFont("Helvetica", 10)
    pdf.drawString(320, y, "Subtotal:")
    pdf.drawRightString(460, y, _format_money(totals["subtotal"]))
    y -= line_gap

    pdf.drawString(320, y, "Discount:")
    pdf.drawRightString(460, y, _format_money(totals["discount"]))
    y -= line_gap

    pdf.drawString(320, y, "VAT:")
    pdf.drawRightString(460, y, _format_money(totals["vat"]))
    y -= line_gap

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(320, y, "Final total:")
    pdf.drawRightString(460, y, _format_money(totals["final_total"]))

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return order, buffer