from __future__ import annotations

from reviews.models import Review


def get_reviewed_product_ids_for_user_and_products(*, user_id: int, product_ids: list[int]) -> set[int]:
    if not user_id or not product_ids:
        return set()

    return set(
        Review.objects.filter(
            customer__user_id=user_id,
            product_id__in=product_ids,
        ).values_list("product_id", flat=True)
    )


def _get_matching_producer_summary_for_order_item(order_item):
    """
    Find the producer summary that belongs to this order item's producer.
    Returns None if no matching summary exists.
    """
    if not getattr(order_item, "order", None) or not getattr(order_item, "producer_id", None):
        return None

    return order_item.order.producer_summaries.filter(
        producer_id=order_item.producer_id
    ).first()


def _is_order_item_shipped(order_item) -> bool:
    summary = _get_matching_producer_summary_for_order_item(order_item)
    if not summary:
        return False

    return summary.status == summary.Status.SHIPPED


def build_review_action_for_order_item(*, order_item, user_id: int, reviewed_product_ids: set[int]) -> dict:
    """
    Review rules stay in the reviews app.
    Orders can call this to get a frontend-friendly payload.
    """
    if not user_id:
        return {
            "eligible": False,
            "already_reviewed": False,
            "label": "Review",
            "reason": "You must be signed in to write a review.",
            "payload": None,
        }

    is_owner = order_item.order.user_id == user_id
    is_shipped = _is_order_item_shipped(order_item)
    already_reviewed = bool(
        order_item.product_id and order_item.product_id in reviewed_product_ids
    )

    eligible = bool(
        order_item.product_id
        and is_owner
        and is_shipped
        and not already_reviewed
    )

    if already_reviewed:
        label = "Reviewed"
        reason = "You have already reviewed this product."
    elif not is_owner:
        label = "Review"
        reason = "You can only review items from your own shipped orders."
    elif not is_shipped:
        label = "Review"
        reason = "Review is available after this item is shipped."
    else:
        label = "Review"
        reason = None

    return {
        "eligible": eligible,
        "already_reviewed": already_reviewed,
        "label": label,
        "reason": reason,
        "payload": {
            "order_id": order_item.order_id,
            "order_item_id": order_item.id,
            "product_id": order_item.product_id,
        } if eligible else {
            "order_id": order_item.order_id,
            "order_item_id": order_item.id,
            "product_id": order_item.product_id,
        },
    }