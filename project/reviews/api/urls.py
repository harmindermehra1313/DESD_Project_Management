from django.urls import path

from reviews.api.views import ProductReviewListAPIView, ReviewCreateAPIView

app_name = "reviews_api"

urlpatterns = [
    path(
        "products/<int:product_id>/reviews/",
        ProductReviewListAPIView.as_view(),
        name="product-reviews",
    ),
    path("", ReviewCreateAPIView.as_view(), name="review-create"),
]