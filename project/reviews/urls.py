from django.urls import path

from reviews.views import (
    ProducerReviewReplyView,
    ProducerReviewsPageView,
    ReviewCreateView,
)

app_name = "reviews"

urlpatterns = [
    path("add/", ReviewCreateView.as_view(), name="add"),
    path(
        "producer/reviews/",
        ProducerReviewsPageView.as_view(),
        name="producer-reviews",
    ),
    path(
        "producer/reviews/<int:review_id>/reply/",
        ProducerReviewReplyView.as_view(),
        name="producer-review-reply",
    ),
]