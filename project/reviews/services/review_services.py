from django.utils import timezone

from reviews.models import Review
from reviews.services.moderation_service import moderate_review_content
from reviews.services.spam_detection_service import detect_review_spam
from orders.models import OrderItem
from orders.services.order_status import get_order_status_context


class ReviewSubmissionError(Exception):
    """Raised when a review submission violates a backend review rule."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        data: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.data = data or {}
        self.detail = {
            "code": code,
            "message": message,
            "data": self.data,
        }
        super().__init__(message)


def _active_quantity(order_item) -> int:
    return max(
        int(order_item.quantity or 0)
        - int(getattr(order_item, "cancelled_quantity", 0) or 0),
        0,
    )


def validate_order_item_review_eligibility(*, user, order_item) -> None:
    order = order_item.order
    status_context = get_order_status_context(order)

    if order.user_id != user.id:
        raise ReviewSubmissionError(
            code="review_order_not_owned",
            message="This order item does not belong to this customer.",
            data={},
        )

    if status_context["status_key"] != "completed":
        raise ReviewSubmissionError(
            code="review_order_not_completed",
            message="Reviews can only be submitted after the order is completed.",
            data={
                "order_id": order.id,
                "order_status": status_context["status_key"],
            },
        )

    if order_item.status == OrderItem.Status.CANCELLED:
        raise ReviewSubmissionError(
            code="review_item_cancelled",
            message="Cancelled items cannot be reviewed.",
            data={
                "order_item_id": order_item.id,
            },
        )

    if _active_quantity(order_item) <= 0:
        raise ReviewSubmissionError(
            code="review_item_no_active_quantity",
            message="Fully refunded or cancelled items cannot be reviewed.",
            data={
                "order_item_id": order_item.id,
            },
        )

    if getattr(order_item, "product_id", None) is None:
        raise ReviewSubmissionError(
            code="review_product_missing",
            message="This product is no longer available for review.",
            data={
                "order_item_id": order_item.id,
            },
        )

    already_reviewed = (
        Review.objects.filter(
            customer=getattr(user, "customer_profile", None),
            product_id=order_item.product_id,
        )
        .exclude(status=Review.Status.REMOVED)
        .exists()
    )

    if already_reviewed:
        raise ReviewSubmissionError(
            code="review_already_submitted",
            message="This product has already been reviewed.",
            data={
                "order_item_id": order_item.id,
            },
        )


def create_review_for_order_item(*, user, order_item, cleaned_data: dict) -> Review:
    customer = getattr(user, "customer_profile", None)

    if customer is None:
        raise ReviewSubmissionError(
            code="review_customer_profile_required",
            message="A customer profile is required to submit a review.",
            data={},
        )

    validate_order_item_review_eligibility(
        user=user,
        order_item=order_item,
    )

    spam_result = detect_review_spam(
        title=cleaned_data["title"],
        review_text=cleaned_data["text"],
    )

    if spam_result.is_spam:
        raise ReviewSubmissionError(
            code="review_spam_detected",
            message="This review appears to contain spam or promotional content.",
            data={
                "reasons": spam_result.reasons,
            },
        )

    moderation_result = moderate_review_content(
        title=cleaned_data["title"],
        text=cleaned_data["text"],
    )

    review = Review(
        customer=customer,
        product=order_item.product,
        order=order_item.order,
        order_item=order_item,
        title=cleaned_data["title"],
        text=cleaned_data["text"],
        rating=cleaned_data["rating"],
        anonymous=cleaned_data.get("anonymous", False),
        moderated_at=timezone.now(),
    )

    notes = []

    if moderation_result.flagged:
        review.status = Review.Status.FLAGGED
        notes.append("Toxic or inappropriate content detected.")
        notes.extend(moderation_result.categories.keys())
    else:
        review.status = Review.Status.PUBLISHED

    review.moderation_notes = "\n".join(notes)

    review.full_clean()
    review.save()
    return review
