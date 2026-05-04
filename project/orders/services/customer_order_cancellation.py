from django.db import transaction
from django.db.models import F
from django.utils import timezone

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
)
from products.models import Inventory
from orders.services.order_status import (
    can_customer_cancel_order,
    sync_order_status_from_producer_summaries,
)
from payments.services import refund_remaining_card_payment_for_order
from notifications.services.notifications import NotificationService


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
        order = Order.objects.select_for_update(of=("self",)).get(pk=order_id)

        if order.user_id != customer.id:
            raise CustomerCancellationError(
                "This order does not belong to this customer."
            )

        if order.status == Order.Status.CANCELLED:
            raise CustomerCancellationError("This order has already been cancelled.")

        if order.status == Order.Status.COMPLETED:
            raise CustomerCancellationError("Completed orders cannot be cancelled.")

        if not can_customer_cancel_order(order):
            raise CustomerCancellationError(
                "This order cannot be cancelled automatically at its current status."
            )

        producer_summaries = ProducerOrderSummary.objects.select_for_update(
            of=("self",)
        ).filter(order=order)

        if producer_summaries.exclude(
            status=ProducerOrderSummary.Status.PENDING
        ).exists():
            raise CustomerCancellationError(
                "This order cannot be cancelled automatically because preparation has already started."
            )

        for item in order.items.select_for_update(of=("self",)).all():
            remaining_active_quantity = item.quantity - item.cancelled_quantity

            if remaining_active_quantity > 0:
                Inventory.objects.filter(pk=item.inventory_id).update(
                    remaining_quantity=F("remaining_quantity")
                    + remaining_active_quantity
                )

            item.cancelled_quantity = item.quantity
            item.status = OrderItem.Status.CANCELLED

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

        sync_order_status_from_producer_summaries(order, save=False)

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
        refund_result = refund_remaining_card_payment_for_order(
            order=order,
            reason=reason,
        )

        NotificationService.notify_order_cancelled(order)

        if refund_result.get("refunded"):
            NotificationService.notify_refund_processed(
                order=order,
                amount=refund_result.get("amount"),
            )

        order.refund_result = refund_result

        return order
