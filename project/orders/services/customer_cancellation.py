from django.db import transaction
from django.db.models import F
from django.utils import timezone

from orders.models import Order, ProducerOrderSummary, ProducerOrderStatusHistory
from products.models import Inventory


class CustomerCancellationError(Exception):
    """Raised when a customer order cancellation is not allowed."""
    pass


def cancel_order_as_customer(
    *,
    order_id,
    customer,
    reason="Customer requested cancellation",
):
    reason = (reason or "").strip() or "Customer requested cancellation"

    with transaction.atomic():
        order = (
            Order.objects
            .select_for_update(of=("self",))
            .get(pk=order_id)
        )

        if order.user_id != customer.id:
            raise CustomerCancellationError(
                "This order does not belong to this customer."
            )

        if order.status == Order.Status.CANCELLED:
            raise CustomerCancellationError(
                "This order has already been cancelled."
            )
        if order.status != Order.Status.PENDING:
            raise CustomerCancellationError(
                "This order cannot be cancelled automatically at its current status."
            )

        if order.status == Order.Status.COMPLETED:
            raise CustomerCancellationError(
                "Completed orders cannot be cancelled."
            )

        producer_summaries = (
            ProducerOrderSummary.objects
            .select_for_update(of=("self",))
            .filter(order=order)
        )

        if producer_summaries.exclude(
            status=ProducerOrderSummary.Status.PENDING
        ).exists():
            raise CustomerCancellationError(
                "This order cannot be cancelled automatically because preparation has already started."
            )

        for item in order.items.all():
            Inventory.objects.filter(pk=item.inventory_id).update(
                remaining_quantity=F("remaining_quantity") + item.quantity
            )

        for summary in producer_summaries:
            old_status = summary.status

            summary.status = ProducerOrderSummary.Status.CANCELLED
            summary.save(update_fields=["status"])

            ProducerOrderStatusHistory.objects.create(
                producer_order_summary=summary,
                old_status=old_status,
                new_status=ProducerOrderSummary.Status.CANCELLED,
                updated_by=customer,
                note=reason,
            )

        order.status = Order.Status.CANCELLED
        order.cancelled_at = timezone.now()
        order.cancelled_by = customer
        order.cancellation_reason = reason
        order.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
            ]
        )

        return order