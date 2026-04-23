from django.core.exceptions import PermissionDenied

from reviews.models import Review



def create_review_for_order_item(*, user, order_item, cleaned_data: dict) -> Review:
    customer = getattr(user, "customer_profile", None)
    if customer is None:
        raise PermissionDenied("A customer profile is required to submit a review.")

    review = Review(
        customer=customer,
        product=order_item.product,
        order=order_item.order,
        order_item=order_item,
        title=cleaned_data["title"],
        text=cleaned_data["text"],
        rating=cleaned_data["rating"],
        anonymous=cleaned_data.get("anonymous", False),
    )

    # Use immediate publication because the public review list and summary only
    # expose PUBLISHED reviews. If moderation is needed, replace this with
    # Review.Status.PENDING and accept that the review will not appear publicly
    # until approved.
    if hasattr(Review, "Status") and hasattr(Review.Status, "PUBLISHED"):
        review.status = Review.Status.PUBLISHED

    review.full_clean()
    review.save()
    return review