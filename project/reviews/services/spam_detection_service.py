"""
DB SHELL TEST:

docker compose exec web python manage.py shell

from reviews.services.spam_detection_service import detect_review_spam

tests = [
    ("Good", "Good product"),
    ("Good product", "visit www.fake-discount.com"),
    ("Best apples!!!", "use promo code FREE123"),
    ("Fresh apples", "Delivery was quick and the apples were good."),
    ("Cheap deal", "Buy now and click here"),
]

for title, text in tests:
    result = detect_review_spam(title, text)
    print("TITLE:", title)
    print("TEXT:", text)
    print("IS SPAM:", result.is_spam)
    print("REASONS:", result.reasons)
    print("-" * 50)
"""

import re
from dataclasses import dataclass


SPAM_MODERATION_NOTE = "Spam or promotional content detected."


@dataclass(frozen=True)
class SpamDetectionResult:
    is_spam: bool
    reasons: list[str]


URL_PATTERN = re.compile(
    r"(https?://|www\.|\b[a-zA-Z0-9-]+\.(com|net|org|co\.uk|io|info)\b)",
    re.IGNORECASE,
)

PROMO_PATTERN = re.compile(
    r"\b("
    r"promo code|discount code|coupon|voucher|use code|code|"
    r"click here|limited offer|buy now|cheap deal|"
    r"free money|telegram|whatsapp"
    r")\b",
    re.IGNORECASE,
)


def detect_review_spam(title: str, review_text: str) -> SpamDetectionResult:
    """
    Detect obvious spam or promotional content.

    The detailed reasons are kept for backend/debugging use.
    Public/admin moderation notes should use SPAM_MODERATION_NOTE only.
    """
    text = f"{title or ''} {review_text or ''}".strip()

    reasons = []

    if URL_PATTERN.search(text):
        reasons.append("External link or website reference detected.")

    if PROMO_PATTERN.search(text):
        reasons.append("Promotional or advertising language detected.")

    return SpamDetectionResult(
        is_spam=bool(reasons),
        reasons=reasons,
    )