from django.urls import path

from orders.api.views.orders import (
    OrderHistoryApiView,
    OrderDetailApiView,
    ReorderOrderApiView,
)

app_name = "orders_api"

urlpatterns = [
    path("history/", OrderHistoryApiView.as_view(), name="order-history"),
    path("<int:order_id>/", OrderDetailApiView.as_view(), name="order-detail"),
    path("<int:order_id>/reorder/", ReorderOrderApiView.as_view(), name="order-reorder"),
]