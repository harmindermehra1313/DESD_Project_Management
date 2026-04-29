"""
DB SHELL TEST: docker compose exec web python manage.py shell

from detoxify import Detoxify

model = Detoxify("unbiased-small")

title = "IDIOTS!!!!"
text = "Only idiots would buy these apples.."

title_scores = model.predict(title)
text_scores = model.predict(text)

scores = {
    category: max(
        float(title_scores.get(category, 0)),
        float(text_scores.get(category, 0)),
    )
    for category in set(title_scores) | set(text_scores)
}

thresholds = {
    "toxicity": 0.90,
    "insult": 0.55,
    "threat": 0.40,
    "identity_attack": 0.40,
    "obscene": 0.70,
    "severe_toxicity": 0.50,
    "sexual_explicit": 0.80,
}

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



@dataclass(frozen=True)
class ModerationResult:
    flagged: bool
    categories: dict
    category_scores: dict


_model = None


def get_model():
    global _model

    if _model is None:
        _model = Detoxify("unbiased-small")

        # Warm-up prediction.
        # This initialises PyTorch/model execution before the first real review.
        _model.predict("Warm up moderation model.")

    return _model


def moderate_review_content(*, title: str, text: str) -> ModerationResult:
    try:
        model = get_model()

        title_text = (title or "").strip()
        body_text = (text or "").strip()

        title_scores = model.predict(title_text) if title_text else {}
        text_scores = model.predict(body_text) if body_text else {}

        scores = {
            category: max(
                float(title_scores.get(category, 0)),
                float(text_scores.get(category, 0)),
            )
            for category in set(title_scores) | set(text_scores)
        }

    except Exception:
        logger.exception(
            "Detoxify moderation failed. Review sent to manual moderation."
        )
        return ModerationResult(
            flagged=True,
            categories={"moderation_error": True},
            category_scores={},
        )

    thresholds = {
        "toxicity": 0.90,
        "insult": 0.55,
        "threat": 0.40,
        "identity_attack": 0.40,
        "obscene": 0.70,
        "severe_toxicity": 0.50,
        "sexual_explicit": 0.80,
    }

    flagged_categories = {
        category: float(score) >= thresholds[category]
        for category, score in scores.items()
        if category in thresholds
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