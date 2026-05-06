from django.utils import timezone

from reviews.models import ReviewProducerResponse
from reviews.services.moderation_service import moderate_review_content
from reviews.services.spam_detection_service import (
    SPAM_MODERATION_NOTE,
    detect_review_spam,
)


TOXIC_MODERATION_NOTE = "Toxic or inappropriate content detected."
MODERATION_ERROR_NOTE = "Automatic moderation could not be completed. Manual review required."


class ProducerResponseError(Exception):
    """Raised when a producer response violates a backend rule."""

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


def _moderation_note_for_result(moderation_result) -> str:
    categories = moderation_result.categories or {}

    if categories.get("moderation_error"):
        return MODERATION_ERROR_NOTE

    return TOXIC_MODERATION_NOTE


def create_or_update_producer_response(*, review, responder, text: str):
    cleaned_text = (text or "").strip()

    if not cleaned_text:
        raise ProducerResponseError(
            code="producer_response_text_required",
            message="Enter a response before submitting.",
            data={},
        )

    if len(cleaned_text) > 2000:
        raise ProducerResponseError(
            code="producer_response_text_too_long",
            message="Producer response must be 2,000 characters or fewer.",
            data={
                "max_length": 2000,
            },
        )

    response, _created = ReviewProducerResponse.objects.get_or_create(
        review=review,
        defaults={
            "responder": responder,
        },
    )

    response.responder = responder
    response.text = cleaned_text
    response.moderated_at = timezone.now()

    spam_result = detect_review_spam(
        title="",
        review_text=cleaned_text,
    )

    if spam_result.is_spam:
        response.status = ReviewProducerResponse.Status.FLAGGED
        response.moderation_notes = SPAM_MODERATION_NOTE
    else:
        moderation_result = moderate_review_content(
            title="",
            text=cleaned_text,
        )

        if moderation_result.flagged:
            response.status = ReviewProducerResponse.Status.FLAGGED
            response.moderation_notes = _moderation_note_for_result(moderation_result)
        else:
            response.status = ReviewProducerResponse.Status.PUBLISHED
            response.moderation_notes = ""

    response.full_clean()
    response.save()

    return response