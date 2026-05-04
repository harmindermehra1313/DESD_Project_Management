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
from products.models import Inventory


class CustomerItemCancellationError(Exception):
    """Raised when a customer item cancellation is not allowed."""
    pass


def _get_producer_summary_for_item(*, order, item):
    return (
        ProducerOrderSummary.objects
        .select_for_update(of=("self",))
        .filter(
            order=order,
            producer_id=item.producer_id,
        )
        .order_by("id")
        .first()
    )


def _cancel_producer_summary_if_all_items_cancelled(
    *,
    order,
    item,
    customer,
    reason,
):
    producer_summary = _get_producer_summary_for_item(
        order=order,
        item=item,
    )

    if producer_summary is None:
        raise CustomerItemCancellationError(
            "Producer order summary was not found for this item."
        )

    has_active_items_for_producer = (
        OrderItem.objects
        .filter(
            order=order,
            producer_id=item.producer_id,
        )
        .exclude(status=OrderItem.Status.CANCELLED)
        .exists()
    )

    if has_active_items_for_producer:
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
        updated_by=customer,
        note=reason,
    )

    return producer_summary


def cancel_order_item_as_customer(
    *,
    order_id,
    order_item_id,
    customer,
    reason="Customer requested item cancellation",
):
    """
    Cancels one item, or part of one item, from a customer order.

    Rules:
    - Order must belong to the logged-in customer.
    - Completed/cancelled orders cannot be changed through automatic cancellation.
    - The item's producer summary must still be Pending.
    - Stock is released only for the cancelled quantity.
    - If all items for that producer become cancelled, the producer summary is cancelled.
    - The main order status is then recalculated from producer summaries.
    """

    reason = (reason or "").strip() or "Customer requested item cancellation"

    with transaction.atomic():
        order = (
            Order.objects
            .select_for_update(of=("self",))
            .get(pk=order_id)
        )

        if order.user_id != customer.id:
            raise CustomerItemCancellationError(
                "This order does not belong to this customer."
            )

        if order.status == Order.Status.CANCELLED:
            raise CustomerItemCancellationError(
                "This order has already been cancelled."
            )

        if order.status == Order.Status.COMPLETED:
            raise CustomerItemCancellationError(
                "Completed orders cannot be cancelled. Please use the refund/support process."
            )

        item = (
            OrderItem.objects
            .select_for_update(of=("self",))
            .get(
                pk=order_item_id,
                order=order,
            )
        )

        producer_summary = _get_producer_summary_for_item(
            order=order,
            item=item,
        )

        if producer_summary is None:
            raise CustomerItemCancellationError(
                "Producer order summary was not found for this item."
            )

        if producer_summary.status != ProducerOrderSummary.Status.PENDING:
            raise CustomerItemCancellationError(
                "This item cannot be cancelled automatically because the producer has already started preparing it."
            )

        remaining_cancellable_quantity = item.quantity - item.cancelled_quantity

        if remaining_cancellable_quantity <= 0:
            raise CustomerItemCancellationError(
                "This item has already been cancelled."
            )

        quantity_to_cancel = remaining_cancellable_quantity

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

        item.cancelled_by = customer
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

        producer_summary = _cancel_producer_summary_if_all_items_cancelled(
            order=order,
            item=item,
            customer=customer,
            reason=reason,
        )

        sync_order_status_from_producer_summaries(order, save=True)
        order.refresh_from_db()

        return {
            "order": order,
            "item": item,
            "producer_summary": producer_summary,
            "cancelled_quantity": quantity_to_cancel,
        }