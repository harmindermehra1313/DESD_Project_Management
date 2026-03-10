from django.urls import path
from carts.api.views.carts import (
    CartAPIView,
    CartItemAddView,
    CartItemDetailView,
    CartMergeAPIView,
)

app_name = "carts_api"

urlpatterns = [
    path("", CartAPIView.as_view(), name="cart"),
    path("items/", CartItemAddView.as_view(), name="cart-item-add"),
    path("items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("merge/", CartMergeAPIView.as_view(), name="cart-merge"),
]
