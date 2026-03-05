from django.urls import path
from . import views
from orders.views.checkout import CheckoutAPIView
from orders.views.checkout import checkout_save, checkout_cod, stripe_return

app_name = "orders"

urlpatterns = [
    path("", views.index, name='index'),
    path("fake-add-to-cart/", views.fake_add_to_cart, name="fake_add_to_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("success/<str:reference>/", views.order_success, name="order_success"),
    path("checkout/api/", CheckoutAPIView.as_view(), name="checkout_api"),
    #path("success/", stripe_return, name="stripe_return"),
    path("success/<str:reference>/", views.order_success, name="order_success"),
    #path("checkout/api/", CheckoutAPIView.as_view(), name="checkout_api"),
    path("checkout/save/", checkout_save, name="checkout_save"),
    path("checkout/return/", stripe_return, name="stripe_return"),
    path("checkout/cod/", checkout_cod, name="checkout_cod"),
]
