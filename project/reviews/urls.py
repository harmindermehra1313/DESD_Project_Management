from django.urls import path

from reviews.views.producer_customer_views import (
    ProducerReviewReplyView,
    ProducerReviewsPageView,
    ReviewCreateView,
)
from reviews.views import admin_moderation_views

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
    path(
        "admin/moderation/",
        admin_moderation_views.admin_review_moderation,
        name="admin_review_moderation",
    ),
    path(
        "admin/moderation/reviews/<int:review_id>/",
        admin_moderation_views.admin_moderate_review,
        name="admin_moderate_review",
    ),
    path(
        "admin/moderation/producer-responses/<int:response_id>/",
        admin_moderation_views.admin_moderate_producer_response,
        name="admin_moderate_producer_response",
    ),
]