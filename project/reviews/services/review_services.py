from django.utils import timezone

from reviews.models import Review
from reviews.services.moderation_service import moderate_review_content
from reviews.services.spam_detection_service import detect_review_spam


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


def create_review_for_order_item(*, user, order_item, cleaned_data: dict) -> Review:
    customer = getattr(user, "customer_profile", None)

    if customer is None:
        raise ReviewSubmissionError(
            code="review_customer_profile_required",
            message="A customer profile is required to submit a review.",
            data={},
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