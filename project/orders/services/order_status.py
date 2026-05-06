from orders.models import Order, ProducerOrderSummary
from notifications.services.notifications import NotificationService


ORDER_STATUS_KEY_BY_CODE = {
    Order.Status.PENDING: "pending",
    Order.Status.IN_PROGRESS: "in_progress",
    Order.Status.PACKAGED: "packaged",
    Order.Status.READY_FOR_COLLECTION: "ready_for_collection",
    Order.Status.COMPLETED: "completed",
    Order.Status.CANCELLED: "cancelled",
}


ORDER_STATUS_PROGRESS_RANK = {
    Order.Status.PENDING: 10,
    Order.Status.IN_PROGRESS: 20,
    Order.Status.PACKAGED: 30,
    Order.Status.READY_FOR_COLLECTION: 40,
    Order.Status.COMPLETED: 50,
}


TERMINAL_ORDER_STATUSES = {
    Order.Status.CANCELLED,
    Order.Status.COMPLETED,
}


OLD_DETAILED_PARENT_STATUSES = {
    Order.Status.PACKAGED,
    Order.Status.READY_FOR_COLLECTION,
}


ACTIVE_PROGRESS_STATUSES = {
    ProducerOrderSummary.Status.PREPARING,
    ProducerOrderSummary.Status.PACKAGED,
    ProducerOrderSummary.Status.READY_FOR_COLLECTION,
    ProducerOrderSummary.Status.SHIPPED,
    ProducerOrderSummary.Status.COMPLETED,
}


def get_order_status_display(status_code):
    try:
        return Order.Status(status_code).label
    except ValueError:
        return str(status_code)


def get_order_status_key(status_code):
    return ORDER_STATUS_KEY_BY_CODE.get(status_code, str(status_code).lower())


def get_order_summaries(order):
    if (
        hasattr(order, "_prefetched_objects_cache")
        and "producer_summaries" in order._prefetched_objects_cache
    ):
        return list(order.producer_summaries.all())

    return list(order.producer_summaries.all())


def has_partial_cancellation(order):
    summaries = get_order_summaries(order)
    items = list(order.items.all())

    summary_partial = False

    if summaries:
        has_cancelled_summary = any(
            summary.status == ProducerOrderSummary.Status.CANCELLED
            for summary in summaries
        )

        has_active_summary = any(
            summary.status != ProducerOrderSummary.Status.CANCELLED
            for summary in summaries
        )

        summary_partial = has_cancelled_summary and has_active_summary

    item_partial = False

    if items:
        has_cancelled_quantity = any(
            getattr(item, "cancelled_quantity", 0) > 0
            for item in items
        )

        has_active_quantity = any(
            getattr(item, "cancelled_quantity", 0) < item.quantity
            for item in items
        )

        item_partial = has_cancelled_quantity and has_active_quantity

    return summary_partial or item_partial


def _get_active_summaries(order):
    return [
        summary
        for summary in get_order_summaries(order)
        if summary.status != ProducerOrderSummary.Status.CANCELLED
    ]


def _derive_raw_order_status_code(order):
    """
    Derives the customer-facing parent order status from producer summaries.

    Main order status is deliberately simple:
    - all producer sections cancelled -> Cancelled
    - all active producer sections pending -> Pending
    - any active producer section being fulfilled -> In progress
    - all active producer sections completed -> Completed

    Detailed fulfilment statuses such as Packaged, Ready for collection, and
    Shipped should be shown at producer/item level, not as the main order badge.
    """

    summaries = get_order_summaries(order)

    if not summaries:
        return order.status

    if all(
        summary.status == ProducerOrderSummary.Status.CANCELLED
        for summary in summaries
    ):
        return Order.Status.CANCELLED

    active_summaries = _get_active_summaries(order)

    if not active_summaries:
        return Order.Status.CANCELLED

    active_statuses = {summary.status for summary in active_summaries}

    if active_statuses == {ProducerOrderSummary.Status.PENDING}:
        return Order.Status.PENDING

    if active_statuses == {ProducerOrderSummary.Status.COMPLETED}:
        return Order.Status.COMPLETED

    if any(status in ACTIVE_PROGRESS_STATUSES for status in active_statuses):
        return Order.Status.IN_PROGRESS

    return Order.Status.IN_PROGRESS


def _prevent_customer_status_regression(order, derived_status):
    """
    Prevents normal backwards movement, but allows old detailed parent statuses
    to be corrected back to In progress.

    This is needed because older logic may already have saved Packaged or Ready
    for collection on the parent Order.status.
    """

    current_status = order.status

    if current_status in TERMINAL_ORDER_STATUSES:
        return current_status

    if derived_status == Order.Status.CANCELLED:
        return Order.Status.CANCELLED

    if (
        current_status in OLD_DETAILED_PARENT_STATUSES
        and derived_status == Order.Status.IN_PROGRESS
    ):
        return derived_status

    current_rank = ORDER_STATUS_PROGRESS_RANK.get(current_status)
    derived_rank = ORDER_STATUS_PROGRESS_RANK.get(derived_status)

    if current_rank is None or derived_rank is None:
        return derived_status

    if derived_rank < current_rank:
        return current_status

    return derived_status


def derive_order_status_code(order):
    raw_status = _derive_raw_order_status_code(order)
    return _prevent_customer_status_regression(order, raw_status)


def can_customer_cancel_order(order):
    """
    Customer automatic cancellation is only allowed while:
    - main order is Pending
    - all producer summaries are still Pending
    """

    if order.status != Order.Status.PENDING:
        return False

    return not order.producer_summaries.exclude(
        status=ProducerOrderSummary.Status.PENDING
    ).exists()


def get_order_status_context(order):
    status_code = derive_order_status_code(order)

    return {
        "status_code": status_code,
        "status_key": get_order_status_key(status_code),
        "status_display": get_order_status_display(status_code),
        "is_partially_cancelled": has_partial_cancellation(order),
        "can_customer_cancel": can_customer_cancel_order(order),
    }


def _is_corrective_parent_status_simplification(old_status, new_status):
    """
    Avoid sending confusing notifications when old parent-level Packaged or
    Ready for collection statuses are corrected back to In progress.
    """

    return (
        old_status in OLD_DETAILED_PARENT_STATUSES
        and new_status == Order.Status.IN_PROGRESS
    )


def sync_order_status_from_producer_summaries(order, save=True):
    old_status = order.status
    status_code = derive_order_status_code(order)

    if old_status != status_code:
        order.status = status_code

        if save:
            order.save(update_fields=["status"])

        should_notify = (
            status_code != Order.Status.CANCELLED
            and not _is_corrective_parent_status_simplification(
                old_status,
                status_code,
            )
        )

        if should_notify:
            NotificationService.notify_order_status_changed(
                order=order,
                old_status=old_status,
                new_status=status_code,
            )

    return order