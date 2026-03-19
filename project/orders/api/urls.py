from django.urls import path

from orders.api.views.reorders import (
    OrderHistoryApiView,
    OrderDetailApiView,
    ReorderOrderApiView,
    ReorderPreviewApiView,
)

app_name = "orders_api"

urlpatterns = [
    path("history/", OrderHistoryApiView.as_view(), name="order-history"),
    path("<int:order_id>/", OrderDetailApiView.as_view(), name="order-detail"),
    path("<int:order_id>/reorder-preview/", ReorderPreviewApiView.as_view(), name="order-reorder-preview"),
    path("<int:order_id>/reorder/", ReorderOrderApiView.as_view(), name="order-reorder"),
]