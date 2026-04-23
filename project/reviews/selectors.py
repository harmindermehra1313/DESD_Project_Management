from __future__ import annotations

from django.db.models import Avg, Count

from reviews.models import Review
from django.core.exceptions import PermissionDenied
from orders.models import OrderItem


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

def get_reviewable_order_item_for_user(
    *,
    user_id: int,
    order_item_id: int,
    order_id: int | None = None,
    product_id: int | None = None,
):
    """
    Resolve and validate an order item that can be reviewed by the current user.
    All review eligibility rules remain inside the reviews app.
    """
    if not user_id:
        raise PermissionDenied("You must be signed in to write a review.")

    order_item = (
        OrderItem.objects.select_related("order", "product", "producer")
        .prefetch_related("order__producer_summaries")
        .get(pk=order_item_id)
    )

    if order_id is not None and order_item.order_id != order_id:
        raise PermissionDenied("This order item does not belong to the selected order.")

    if product_id is not None and order_item.product_id != product_id:
        raise PermissionDenied("This order item does not match the selected product.")

    product_ids = [order_item.product_id] if order_item.product_id else []
    reviewed_product_ids = get_reviewed_product_ids_for_user_and_products(
        user_id=user_id,
        product_ids=product_ids,
    )

    action = build_review_action_for_order_item(
        order_item=order_item,
        user_id=user_id,
        reviewed_product_ids=reviewed_product_ids,
    )

    if not action["eligible"]:
        raise PermissionDenied(action.get("reason") or "Review is not available for this item.")

    return order_item


def get_published_reviews_for_product(*, product_id: int):
    return (
        Review.objects.filter(
            product_id=product_id,
            status=Review.Status.PUBLISHED,
        )
        .select_related("customer__user")
        .order_by("-created_at", "-id")
    )



def get_published_review_summary_for_product(*, product_id: int) -> dict:
    qs = Review.objects.filter(
        product_id=product_id,
        status=Review.Status.PUBLISHED,
    )

    aggregate = qs.aggregate(
        review_count=Count("id"),
        average_rating=Avg("rating"),
    )

    rating_breakdown = {str(rating): 0 for rating in range(1, 6)}
    for row in qs.values("rating").annotate(count=Count("id")):
        rating_breakdown[str(row["rating"])] = row["count"]

    average_rating = aggregate["average_rating"]

    return {
        "review_count": aggregate["review_count"] or 0,
        "average_rating": round(float(average_rating), 2) if average_rating is not None else 0.0,
        "rating_breakdown": rating_breakdown,
    }