"""
DB SHELL TEST:

docker compose exec web python manage.py shell

from reviews.services.moderation_service import moderate_review_content

result = moderate_review_content(
    title="IDIOTS!!!!",
    text="Only idiots would buy these apples..",
)

print(result.category_scores)
print(result.categories)
print(result.flagged)
"""

import logging
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)

# Reduce noisy model-download/network logs.
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)


THRESHOLDS = {
    "toxicity": 0.90,
    "insult": 0.55,
    "threat": 0.40,
    "identity_attack": 0.40,
    "obscene": 0.70,
    "severe_toxicity": 0.50,
    "sexual_explicit": 0.80,
}

<<<<<<< HEAD
flagged_categories = {
    category: score >= thresholds[category]
    for category, score in scores.items()
    if category in thresholds
}

print(scores)
print(flagged_categories)
print(any(flagged_categories.values()))
"""

import logging
from dataclasses import dataclass

from detoxify import Detoxify


=======
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64

@dataclass(frozen=True)
class ModerationResult:
    flagged: bool
    categories: dict
    category_scores: dict


_model = None
_model_lock = Lock()


def _flagged_moderation_error() -> ModerationResult:
    """
    Safe fallback.

    If Detoxify cannot import, load, download, warm up, or predict,
    the content must not be published automatically.
    It is sent to flagged moderation instead.
    """
    return ModerationResult(
        flagged=True,
        categories={
            "moderation_error": True,
        },
        category_scores={},
    )


def get_model():
    """
    Load and cache the Detoxify model once per Python process.

    Detoxify is imported inside this function so that a missing or broken
    Detoxify installation does not crash Django during module import.
    """
    global _model

    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        try:
            from detoxify import Detoxify

            model = Detoxify("unbiased-small")

            # Warm-up prediction.
            # This initialises PyTorch/model execution before the first real review.
            model.predict("Warm up moderation model.")

            _model = model
            logger.info("Review moderation model loaded successfully.")

        except Exception:
            logger.exception(
                "Review moderation model could not be loaded. "
                "Affected content will be sent to flagged moderation."
            )
            raise

    return _model


def moderate_review_content(*, title: str, text: str) -> ModerationResult:
    """
    Moderate review title and body text using Detoxify.

    If Detoxify is unavailable or fails, return a flagged moderation result
    so the review/response goes to manual moderation instead of being published.
    """
    try:
        model = get_model()

        title_text = (title or "").strip()
        body_text = (text or "").strip()

        title_scores = model.predict(title_text) if title_text else {}
        body_scores = model.predict(body_text) if body_text else {}

        scores = {
            category: max(
                float(title_scores.get(category, 0)),
                float(body_scores.get(category, 0)),
            )
            for category in set(title_scores) | set(body_scores)
        }

    except Exception:
        logger.exception(
            "Error during review content moderation. "
            "Content will be sent to flagged moderation."
        )
        return _flagged_moderation_error()

    flagged_categories = {
        category: float(scores.get(category, 0)) >= threshold
        for category, threshold in THRESHOLDS.items()
    }

    category_scores = {
        category: float(score)
        for category, score in scores.items()
    }

    return ModerationResult(
        flagged=any(flagged_categories.values()),
        categories=flagged_categories,
        category_scores=category_scores,
    )