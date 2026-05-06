from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
)
from orders.services.order_status import sync_order_status_from_producer_summaries
from payments.services import refund_cancelled_order_item
from products.models import Inventory
from notifications.services.notifications import NotificationService


class ProducerItemCancellationError(Exception):
    """Raised when a producer item cancellation is not allowed."""

    pass


COMMISSION_RATE = Decimal("0.05")


CANCELLABLE_PRODUCER_ITEM_STATUSES = {
    ProducerOrderSummary.Status.PENDING,
    ProducerOrderSummary.Status.PREPARING,
    ProducerOrderSummary.Status.PACKAGED,
    ProducerOrderSummary.Status.READY_FOR_COLLECTION,
}


def _money(amount):
    return Decimal(amount).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _active_quantity(item):
    return max(item.quantity - item.cancelled_quantity, 0)


def _get_producer_summary_for_item(*, order, item):
    return (
        ProducerOrderSummary.objects.select_for_update(of=("self",))
        .filter(
            order=order,
            producer_id=item.producer_id,
        )
        .order_by("id")
        .first()
    )


def _recalculate_producer_summary_totals(producer_summary):
    items = OrderItem.objects.select_for_update(of=("self",)).filter(
        order=producer_summary.order,
        producer=producer_summary.producer,
    )

    active_subtotal = Decimal("0.00")
    active_vat_total = Decimal("0.00")

    for item in items:
        active_qty = Decimal(_active_quantity(item))

        if active_qty <= 0:
            continue

        unit_price = Decimal(item.final_unit_price)
        vat_rate = Decimal(item.vat_rate or 0)

        active_subtotal += unit_price * active_qty
        active_vat_total += unit_price * active_qty * (vat_rate / Decimal("100"))

    active_commission_total = active_subtotal * COMMISSION_RATE
    active_payout_amount = active_subtotal - active_commission_total

    producer_summary.subtotal = _money(active_subtotal)
    producer_summary.vat_total = _money(active_vat_total)
    producer_summary.commission_total = _money(active_commission_total)
    producer_summary.payout_amount = _money(active_payout_amount)

    producer_summary.save(
        update_fields=[
            "subtotal",
            "vat_total",
            "commission_total",
            "payout_amount",
        ]
    )

    return producer_summary


def _cancel_summary_if_no_active_items(*, producer_summary, cancelled_by, reason):
    has_active_items = (
        OrderItem.objects.filter(
            order=producer_summary.order,
            producer=producer_summary.producer,
        )
        .exclude(status=OrderItem.Status.CANCELLED)
        .exists()
    )

    if has_active_items:
        return producer_summary

    if producer_summary.status == ProducerOrderSummary.Status.CANCELLED:
        return producer_summary

    old_status = producer_summary.status
    producer_summary.status = ProducerOrderSummary.Status.CANCELLED
    producer_summary.save(update_fields=["status"])

    ProducerOrderStatusHistory.objects.create(
        producer_order_summary=producer_summary,
        old_status=old_status,
        new_status=ProducerOrderSummary.Status.CANCELLED,
        updated_by=cancelled_by,
        note=reason,
    )

    return producer_summary


def cancel_producer_order_item_as_producer(
    *,
    order_item_id,
    producer,
    cancelled_by,
    quantity_to_cancel=None,
    reason="Producer cancelled this item",
):
    reason = (reason or "").strip() or "Producer cancelled this item"

    with transaction.atomic():
        item = (
            OrderItem.objects.select_for_update(of=("self",))
            .select_related("order", "inventory", "product")
            .get(
                id=order_item_id,
                producer=producer,
            )
        )

        order = Order.objects.select_for_update(of=("self",)).get(
            id=item.order_id,
        )

        if order.status == Order.Status.CANCELLED:
            raise ProducerItemCancellationError(
                "This order has already been cancelled."
            )

        if order.status == Order.Status.COMPLETED:
            raise ProducerItemCancellationError(
                "This order has already been completed."
            )

        producer_summary = _get_producer_summary_for_item(
            order=order,
            item=item,
        )

        if producer_summary is None:
            raise ProducerItemCancellationError(
                "Producer order summary was not found for this item."
            )

        if producer_summary.status == ProducerOrderSummary.Status.CANCELLED:
            raise ProducerItemCancellationError(
                "This producer order has already been cancelled."
            )

        if producer_summary.status == ProducerOrderSummary.Status.COMPLETED:
            raise ProducerItemCancellationError(
                "This producer order has already been completed."
            )

        if producer_summary.status == ProducerOrderSummary.Status.SHIPPED:
            raise ProducerItemCancellationError(
                "This item cannot be cancelled automatically because the producer order has already been shipped."
            )

        if producer_summary.status not in CANCELLABLE_PRODUCER_ITEM_STATUSES:
            raise ProducerItemCancellationError(
                "This item cannot be cancelled automatically at the current producer order status."
            )

        active_quantity = _active_quantity(item)

        if active_quantity <= 0:
            raise ProducerItemCancellationError(
                "This item has already been cancelled."
            )

        if quantity_to_cancel is None:
            quantity_to_cancel = active_quantity

        try:
            quantity_to_cancel = int(quantity_to_cancel)
        except (TypeError, ValueError):
            raise ProducerItemCancellationError(
                "Cancellation quantity must be a whole number."
            )

        if quantity_to_cancel <= 0:
            raise ProducerItemCancellationError(
                "Cancellation quantity must be at least 1."
            )

        if quantity_to_cancel > active_quantity:
            raise ProducerItemCancellationError(
                f"Cannot cancel {quantity_to_cancel}. Only {active_quantity} active item(s) remain."
            )

        Inventory.objects.filter(pk=item.inventory_id).update(
            remaining_quantity=F("remaining_quantity") + quantity_to_cancel
        )

        item.cancelled_quantity += quantity_to_cancel

        if item.cancelled_quantity >= item.quantity:
            item.status = OrderItem.Status.CANCELLED
        else:
            item.status = OrderItem.Status.PARTIALLY_CANCELLED

        if item.cancelled_at is None:
            item.cancelled_at = timezone.now()

        item.cancelled_by = cancelled_by
        item.cancellation_reason = reason
        item.save(
            update_fields=[
                "status",
                "cancelled_quantity",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
            ]
        )

        producer_summary = _recalculate_producer_summary_totals(producer_summary)

        producer_summary = _cancel_summary_if_no_active_items(
            producer_summary=producer_summary,
            cancelled_by=cancelled_by,
            reason=reason,
        )

        sync_order_status_from_producer_summaries(order, save=True)
        order.refresh_from_db()

        refund_result = refund_cancelled_order_item(
            order=order,
            item=item,
            cancelled_quantity=quantity_to_cancel,
            reason=reason,
            cancellation_marker=f"cancelled-total-{item.cancelled_quantity}",
        )

        NotificationService.notify_order_item_cancelled(
            order=order,
            item=item,
            cancelled_quantity=quantity_to_cancel,
        )

        if refund_result.get("refunded"):
            NotificationService.notify_refund_processed(
                order=order,
                amount=refund_result.get("amount"),
            )

        return {
            "order": order,
            "item": item,
            "producer_summary": producer_summary,
            "cancelled_quantity": quantity_to_cancel,
            "refund": refund_result,
        }