from django.urls import path

from reviews.api.views import (
    ProducerReviewListAPIView,
    ProducerReviewResponseAPIView,
    ProductReviewListAPIView,
    ReviewCreateAPIView,
)

app_name = "reviews_api"

urlpatterns = [
    path(
        "products/<int:product_id>/reviews/",
        ProductReviewListAPIView.as_view(),
        name="product-reviews",
    ),
    path(
        "producer/reviews/",
        ProducerReviewListAPIView.as_view(),
        name="producer-reviews",
    ),
    path(
        "<int:review_id>/producer-response/",
        ProducerReviewResponseAPIView.as_view(),
        name="producer-review-response",
    ),
    path("", ReviewCreateAPIView.as_view(), name="review-create"),
]