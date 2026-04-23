from django.core.exceptions import PermissionDenied
from django.utils import timezone

from reviews.models import Review
from reviews.services.moderation_service import moderate_review_content


def create_review_for_order_item(*, user, order_item, cleaned_data: dict) -> Review:
    customer = getattr(user, "customer_profile", None)
    if customer is None:
        raise PermissionDenied("A customer profile is required to submit a review.")

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

    if moderation_result.flagged:
        review.status = Review.Status.FLAGGED
    else:
        review.status = Review.Status.PUBLISHED

    review.full_clean()
    review.save()
    return review