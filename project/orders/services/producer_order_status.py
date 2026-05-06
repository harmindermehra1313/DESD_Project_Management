from django.db import transaction

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
)
from orders.services.order_status import sync_order_status_from_producer_summaries
from notifications.services.notifications import NotificationService


class ProducerOrderStatusError(Exception):
    """Raised when a producer order status change is not allowed."""

    pass


DELIVERY_TRANSITIONS = {
    ProducerOrderSummary.Status.PENDING: {
        ProducerOrderSummary.Status.PREPARING,
    },
    ProducerOrderSummary.Status.PREPARING: {
        ProducerOrderSummary.Status.PACKAGED,
    },
    ProducerOrderSummary.Status.PACKAGED: {
        ProducerOrderSummary.Status.SHIPPED,
    },
    ProducerOrderSummary.Status.SHIPPED: {
        ProducerOrderSummary.Status.COMPLETED,
    },
    ProducerOrderSummary.Status.COMPLETED: set(),
    ProducerOrderSummary.Status.CANCELLED: set(),
}


COLLECTION_TRANSITIONS = {
    ProducerOrderSummary.Status.PENDING: {
        ProducerOrderSummary.Status.PREPARING,
    },
    ProducerOrderSummary.Status.PREPARING: {
        ProducerOrderSummary.Status.PACKAGED,
    },
    ProducerOrderSummary.Status.PACKAGED: {
        ProducerOrderSummary.Status.READY_FOR_COLLECTION,
    },
    ProducerOrderSummary.Status.READY_FOR_COLLECTION: {
        ProducerOrderSummary.Status.COMPLETED,
    },
    ProducerOrderSummary.Status.COMPLETED: set(),
    ProducerOrderSummary.Status.CANCELLED: set(),
}


ITEM_NOTIFICATION_STATUSES = {
    ProducerOrderSummary.Status.PACKAGED,
    ProducerOrderSummary.Status.READY_FOR_COLLECTION,
    ProducerOrderSummary.Status.SHIPPED,
    ProducerOrderSummary.Status.COMPLETED,
}


def get_allowed_next_statuses(summary):
    if summary.status in {
        ProducerOrderSummary.Status.CANCELLED,
        ProducerOrderSummary.Status.COMPLETED,
    }:
        return set()

    if summary.delivery_or_collection == Order.DeliveryOrCollection.DELIVERY:
        return DELIVERY_TRANSITIONS.get(summary.status, set())

    if summary.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION:
        return COLLECTION_TRANSITIONS.get(summary.status, set())

    return set()


def validate_next_status(summary, new_status):
    if new_status == summary.status:
        return

    if new_status == ProducerOrderSummary.Status.CANCELLED:
        raise ProducerOrderStatusError(
            "Cancellation must use the producer cancellation workflow."
        )

    allowed_statuses = get_allowed_next_statuses(summary)

    if new_status not in allowed_statuses:
        current_label = summary.get_status_display()

        try:
            new_label = ProducerOrderSummary.Status(new_status).label
        except ValueError:
            new_label = str(new_status)

        raise ProducerOrderStatusError(
            f"Cannot move producer order from {current_label} to {new_label}."
        )


def _get_active_items_for_summary(summary):
    return list(
        OrderItem.objects.select_related("product", "producer")
        .filter(
            order=summary.order,
            producer=summary.producer,
        )
        .exclude(status=OrderItem.Status.CANCELLED)
        .order_by("id")
    )


def update_producer_order_status(
    *,
    summary_id,
    producer,
    updated_by,
    new_status,
    note="Status updated via Producer Dashboard",
):
    """
    Updates one producer's own order section.

    Rules:
    - Producer can only update their own summary.
    - Status cannot go backwards.
    - Delivery and collection have different valid flows.
    - Cancellation is excluded from this workflow.
    - Parent order status is recalculated after the producer status changes.
    - Customer receives item-level notifications for useful fulfilment milestones.
    """

    note = (note or "").strip() or "Status updated via Producer Dashboard"

    with transaction.atomic():
        summary = (
            ProducerOrderSummary.objects.select_for_update(of=("self",))
            .select_related("order", "producer")
            .get(
                id=summary_id,
                producer=producer,
            )
        )

        order = Order.objects.select_for_update(of=("self",)).get(
            id=summary.order_id
        )

        if order.status == Order.Status.CANCELLED:
            raise ProducerOrderStatusError(
                "This order has already been cancelled."
            )

        if order.status == Order.Status.COMPLETED:
            raise ProducerOrderStatusError(
                "This order has already been completed."
            )

        validate_next_status(summary, new_status)

        old_status = summary.status

        if old_status == new_status:
            return {
                "success": True,
                "changed": False,
                "summary": summary,
                "order": order,
            }

        summary.status = new_status
        summary.save(update_fields=["status"])

        ProducerOrderStatusHistory.objects.create(
            producer_order_summary=summary,
            old_status=old_status,
            new_status=new_status,
            updated_by=updated_by,
            note=note,
        )

        active_items = _get_active_items_for_summary(summary)

        if new_status in ITEM_NOTIFICATION_STATUSES:
            NotificationService.notify_order_items_producer_status_changed(
                order=order,
                producer_summary=summary,
                items=active_items,
                new_status=new_status,
            )

        sync_order_status_from_producer_summaries(order, save=True)
        order.refresh_from_db()

        return {
            "success": True,
            "changed": True,
            "summary": summary,
            "order": order,
        }