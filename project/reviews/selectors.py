from __future__ import annotations

from django.db.models import Avg, Count

from reviews.models import Review
from django.core.exceptions import PermissionDenied
from orders.models import OrderItem
from django.db.models.functions import Coalesce
from orders.services.order_status import get_order_status_context


def get_reviewed_product_ids_for_user_and_products(
    *, user_id: int, product_ids: list[int]
) -> set[int]:
    if not user_id or not product_ids:
        return set()

    return set(
        Review.objects.filter(
            customer__user_id=user_id,
            product_id__in=product_ids,
        )
        .exclude(status=Review.Status.REMOVED)
        .values_list("product_id", flat=True)
    )


def _active_quantity(order_item) -> int:
    return max(
        int(order_item.quantity or 0)
        - int(getattr(order_item, "cancelled_quantity", 0) or 0),
        0,
    )


def _build_review_payload(order_item) -> dict:
    return {
        "order_id": order_item.order_id,
        "order_item_id": order_item.id,
        "product_id": order_item.product_id,
    }


def build_review_action_for_order_item(
    *, order_item, user_id: int, reviewed_product_ids: set[int]
) -> dict:
    """
    Build the frontend review action for one order item.

    Review eligibility rules:
    - user must be signed in
    - order item must belong to the signed-in customer
    - derived main order status must be completed
    - item must not be fully cancelled/refunded
    - product must still exist on the order item
    - product must not already have a review from this customer
    """
    if not user_id:
        return {
            "eligible": False,
            "already_reviewed": False,
            "label": "Review",
            "reason": "Sign in to write a review.",
            "payload": None,
        }

    payload = _build_review_payload(order_item)
    is_owner = order_item.order.user_id == user_id
    active_quantity = _active_quantity(order_item)
    status_context = get_order_status_context(order_item.order)

    already_reviewed = bool(
        order_item.product_id and order_item.product_id in reviewed_product_ids
    )

    if already_reviewed:
        return {
            "eligible": False,
            "already_reviewed": True,
            "label": "Reviewed",
            "reason": "This product has already been reviewed.",
            "payload": payload,
        }

    if not is_owner:
        return {
            "eligible": False,
            "already_reviewed": False,
            "label": "Review",
            "reason": "Only items from this customer account can be reviewed.",
            "payload": payload,
        }

    if not order_item.product_id:
        return {
            "eligible": False,
            "already_reviewed": False,
            "label": "Review",
            "reason": "This product is no longer available for review.",
            "payload": payload,
        }

    if status_context["status_key"] != "completed":
        return {
            "eligible": False,
            "already_reviewed": False,
            "label": "Review",
            "reason": "Review is available after the order is completed.",
            "payload": payload,
        }

    if order_item.status == OrderItem.Status.CANCELLED or active_quantity <= 0:
        return {
            "eligible": False,
            "already_reviewed": False,
            "label": "Review",
            "reason": "Cancelled or fully refunded items cannot be reviewed.",
            "payload": payload,
        }

    return {
        "eligible": True,
        "already_reviewed": False,
        "label": "Review",
        "reason": None,
        "payload": payload,
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
        .prefetch_related("order__producer_summaries", "order__items")
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
        raise PermissionDenied(
            action.get("reason") or "Review is not available for this item."
        )

    return order_item


def get_published_reviews_for_product(*, product_id: int):
    return (
        Review.objects.filter(
            product_id=product_id,
            status=Review.Status.PUBLISHED,
        )
        .select_related(
            "customer__user",
            "product",
            "product__producer",
            "producer_response",
            "producer_response__responder",
        )
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
        "average_rating": (
            round(float(average_rating), 2) if average_rating is not None else 0.0
        ),
        "rating_breakdown": rating_breakdown,
    }


def get_producer_profile_for_user(user):
    """
    Resolve the producer profile for the logged-in producer user.

    If the project uses a different reverse relation name, only this helper
    should need changing.
    """
    if not user or not user.is_authenticated:
        return None

    possible_attrs = (
        "producer_profile",
        "producerprofile",
        "producer",
    )

    for attr in possible_attrs:
        producer = getattr(user, attr, None)

        if producer is not None:
            return producer

    return None


def get_reviews_for_producer(*, producer):
    """
    Return published product reviews belonging to this producer.

    latest_activity_at means:
    - producer response updated_at, if a response exists
    - otherwise customer review created_at
    """
    return (
        Review.objects.filter(
            product__producer=producer,
            status=Review.Status.PUBLISHED,
        )
        .select_related(
            "customer__user",
            "product",
            "product__producer",
            "producer_response",
            "producer_response__responder",
        )
        .annotate(
            latest_activity_at=Coalesce(
                "producer_response__updated_at",
                "created_at",
            )
        )
        .order_by("-latest_activity_at", "-created_at", "-id")
    )


def get_producer_owned_review_or_404(*, review_id: int, producer):
    return Review.objects.select_related(
        "customer__user",
        "product",
        "product__producer",
        "producer_response",
        "producer_response__responder",
    ).get(
        id=review_id,
        product__producer=producer,
        status=Review.Status.PUBLISHED,
    )
