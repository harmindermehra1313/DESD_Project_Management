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
from payments.services import create_customer_refund
from notifications.services.notifications import NotificationService
from products.models import Inventory


class ProducerOrderCancellationError(Exception):
    """Raised when a producer order cancellation is not allowed."""

    pass


CANCELLABLE_PRODUCER_STATUSES = {
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


def _refund_amount_for_item(item, quantity):
    """
    Refunds the customer-facing item amount.

    This includes item unit price plus the proportional VAT stored on the item.
    If VAT is always zero in the current dataset, this still returns the same result
    as unit_price * quantity.
    """
    quantity = Decimal(quantity)

    if item.quantity <= 0:
        return Decimal("0.00")

    unit_price_total = Decimal(item.final_unit_price) * quantity
    vat_per_unit = Decimal(item.vat_amount or 0) / Decimal(item.quantity)

    return unit_price_total + (vat_per_unit * quantity)


def cancel_producer_order_as_producer(
    *,
    summary_id,
    producer,
    cancelled_by,
    reason="Producer cancelled this order section",
):
    """
    Cancels one producer's section of an order.

    Rules:
    - Producer can only cancel their own ProducerOrderSummary.
    - Completed, shipped, or already cancelled producer sections cannot be cancelled automatically.
    - Only this producer's active items are cancelled.
    - Stock is returned for the active quantity.
    - Producer payout values are zeroed.
    - Customer is refunded for this producer section.
    - Parent order status is recalculated.
    """

    reason = (reason or "").strip() or "Producer cancelled this order section"

    with transaction.atomic():
        summary = (
            ProducerOrderSummary.objects.select_for_update(of=("self",))
            .select_related("order")
            .get(
                id=summary_id,
                producer=producer,
            )
        )

        order = Order.objects.select_for_update(of=("self",)).get(
            id=summary.order_id,
        )

        if order.status == Order.Status.CANCELLED:
            raise ProducerOrderCancellationError(
                "This order has already been cancelled."
            )

        if order.status == Order.Status.COMPLETED:
            raise ProducerOrderCancellationError(
                "This order has already been completed."
            )

        if summary.status == ProducerOrderSummary.Status.CANCELLED:
            raise ProducerOrderCancellationError(
                "This producer order has already been cancelled."
            )

        if summary.status not in CANCELLABLE_PRODUCER_STATUSES:
            raise ProducerOrderCancellationError(
                "This producer order cannot be cancelled automatically at its current status."
            )

        items = list(
            OrderItem.objects.select_for_update(of=("self",))
            .filter(
                order=order,
                producer=producer,
            )
            .select_related("inventory", "product")
        )

        if not items:
            raise ProducerOrderCancellationError(
                "No items were found for this producer order."
            )

        refund_amount = Decimal("0.00")
        cancelled_items = []

        for item in items:
            active_quantity = _active_quantity(item)

            if active_quantity <= 0:
                continue

            Inventory.objects.filter(pk=item.inventory_id).update(
                remaining_quantity=F("remaining_quantity") + active_quantity
            )

            refund_amount += _refund_amount_for_item(item, active_quantity)

            item.cancelled_quantity = item.quantity
            item.status = OrderItem.Status.CANCELLED

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

            cancelled_items.append(
                {
                    "item": item,
                    "cancelled_quantity": active_quantity,
                }
            )

        if refund_amount <= Decimal("0.00"):
            raise ProducerOrderCancellationError(
                "There are no active items left to cancel."
            )

        old_status = summary.status
        summary.status = ProducerOrderSummary.Status.CANCELLED
        summary.subtotal = Decimal("0.00")
        summary.vat_total = Decimal("0.00")
        summary.commission_total = Decimal("0.00")
        summary.payout_amount = Decimal("0.00")
        summary.save(
            update_fields=[
                "status",
                "subtotal",
                "vat_total",
                "commission_total",
                "payout_amount",
            ]
        )

        ProducerOrderStatusHistory.objects.create(
            producer_order_summary=summary,
            old_status=old_status,
            new_status=ProducerOrderSummary.Status.CANCELLED,
            updated_by=cancelled_by,
            note=reason,
        )

        sync_order_status_from_producer_summaries(order, save=True)
        order.refresh_from_db()

        if order.status == Order.Status.CANCELLED:
            order.cancelled_at = timezone.now()
            order.cancelled_by = cancelled_by
            order.cancellation_reason = reason
            order.save(
                update_fields=[
                    "cancelled_at",
                    "cancelled_by",
                    "cancellation_reason",
                ]
            )

        refund_result = create_customer_refund(
            order=order,
            amount=_money(refund_amount),
            reason=reason,
            order_item=None,
            idempotency_key=f"order-{order.id}-producer-summary-{summary.id}-producer-refund",
        )

        if order.status == Order.Status.CANCELLED:
            NotificationService.notify_order_cancelled(order)
        else:
            for cancelled_item in cancelled_items:
                NotificationService.notify_order_item_cancelled(
                    order=order,
                    item=cancelled_item["item"],
                    cancelled_quantity=cancelled_item["cancelled_quantity"],
                )

        if refund_result.get("refunded"):
            NotificationService.notify_refund_processed(
                order=order,
                amount=refund_result.get("amount"),
            )

        return {
            "order": order,
            "summary": summary,
            "cancelled_items": cancelled_items,
            "refund": refund_result,
        }