from orders.models import Order, ProducerOrderSummary


ORDER_STATUS_KEY_BY_CODE = {
    Order.Status.PENDING: "pending",
    Order.Status.IN_PROGRESS: "in_progress",
    Order.Status.PACKAGED: "packaged",
    Order.Status.READY_FOR_COLLECTION: "ready_for_collection",
    Order.Status.COMPLETED: "completed",
    Order.Status.CANCELLED: "cancelled",
}


def get_order_status_display(status_code):
    try:
        return Order.Status(status_code).label
    except ValueError:
        return str(status_code)


def get_order_status_key(status_code):
    return ORDER_STATUS_KEY_BY_CODE.get(status_code, str(status_code).lower())


def get_order_summaries(order):
    if hasattr(order, "_prefetched_objects_cache") and "producer_summaries" in order._prefetched_objects_cache:
        return list(order.producer_summaries.all())

    return list(order.producer_summaries.all())


def has_partial_cancellation(order):
    summaries = get_order_summaries(order)

    if not summaries:
        return False

    has_cancelled = any(
        summary.status == ProducerOrderSummary.Status.CANCELLED
        for summary in summaries
    )

    has_active = any(
        summary.status != ProducerOrderSummary.Status.CANCELLED
        for summary in summaries
    )

    return has_cancelled and has_active


def derive_order_status_code(order):
    """
    Derives the customer-facing order status from producer summaries.

    Important edge cases:
    - One producer summary cancelled -> whole order cancelled.
    - All producer summaries cancelled -> whole order cancelled.
    - Some producer summaries cancelled but others active -> order remains active.
    - All active producer summaries completed -> completed.
    - All active collection summaries packaged -> ready for collection.
    - Delivery orders do not become ready for collection.
    """

    summaries = get_order_summaries(order)

    if not summaries:
        return order.status

    if all(
        summary.status == ProducerOrderSummary.Status.CANCELLED
        for summary in summaries
    ):
        return Order.Status.CANCELLED

    if order.status == Order.Status.CANCELLED:
        return Order.Status.CANCELLED

    active_summaries = [
        summary
        for summary in summaries
        if summary.status != ProducerOrderSummary.Status.CANCELLED
    ]

    if not active_summaries:
        return Order.Status.CANCELLED

    active_statuses = {summary.status for summary in active_summaries}

    if active_statuses == {ProducerOrderSummary.Status.PENDING}:
        return Order.Status.PENDING

    if active_statuses == {ProducerOrderSummary.Status.COMPLETED}:
        return Order.Status.COMPLETED

    unfinished_active_summaries = [
        summary
        for summary in active_summaries
        if summary.status != ProducerOrderSummary.Status.COMPLETED
    ]

    if (
        unfinished_active_summaries
        and all(
            summary.status == ProducerOrderSummary.Status.PACKAGED
            for summary in unfinished_active_summaries
        )
        and all(
            summary.delivery_or_collection == Order.DeliveryOrCollection.COLLECTION
            for summary in unfinished_active_summaries
        )
    ):
        return Order.Status.READY_FOR_COLLECTION

    if any(
        status in {
            ProducerOrderSummary.Status.PREPARING,
            ProducerOrderSummary.Status.PACKAGED,
            ProducerOrderSummary.Status.SHIPPED,
            ProducerOrderSummary.Status.COMPLETED,
        }
        for status in active_statuses
    ):
        return Order.Status.IN_PROGRESS

    return Order.Status.IN_PROGRESS


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


def sync_order_status_from_producer_summaries(order, save=True):
    status_code = derive_order_status_code(order)

    if order.status != status_code:
        order.status = status_code

        if save:
            order.save(update_fields=["status"])

    return order