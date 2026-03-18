from django.urls import path
from . import views
from orders.views.checkout import checkout_save, checkout_cod, stripe_return
from .views.order_history import order_history_page

app_name = "orders"

urlpatterns = [
    path("", views.index, name='index'),
    path("checkout/", views.checkout, name="checkout"),
    path("success/<str:reference>/", views.order_success, name="order_success"),
    path("checkout/save/", checkout_save, name="checkout_save"),
    path("checkout/return/", stripe_return, name="stripe_return"),
    path("checkout/cod/", checkout_cod, name="checkout_cod"),
    # Order history
    path("order-history/", order_history_page, name="order-history-page"),
]
