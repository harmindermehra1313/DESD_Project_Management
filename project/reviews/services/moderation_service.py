import logging
from dataclasses import dataclass

from django.conf import settings
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModerationResult:
    flagged: bool
    categories: dict
    category_scores: dict


def moderate_review_content(*, title: str, text: str) -> ModerationResult:
    """
    Moderates review title and text using OpenAI Moderation.

    flagged=True means the review should not be published automatically.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", None)

    if not api_key:
        logger.warning("OPENAI_API_KEY is missing. Review moderation skipped.")
        return ModerationResult(
            flagged=False,
            categories={},
            category_scores={},
        )

    client = OpenAI(api_key=api_key)

    review_input = f"Review title: {title}\n\nReview text: {text}"

    try:
        response = client.moderations.create(
            model=getattr(
                settings,
                "OPENAI_MODERATION_MODEL",
                "omni-moderation-latest",
            ),
            input=review_input,
        )
    except OpenAIError:
        logger.exception("OpenAI moderation failed. Review marked as flagged.")
        return ModerationResult(
            flagged=True,
            categories={"moderation_api_error": True},
            category_scores={},
        )

    result = response.results[0]

    return ModerationResult(
        flagged=bool(result.flagged),
        categories=dict(result.categories),
        category_scores=dict(result.category_scores),
    )