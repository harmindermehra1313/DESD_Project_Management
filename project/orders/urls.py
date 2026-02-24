from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("", views.index, name='index'),
    path("fake-add-to-cart/", views.fake_add_to_cart, name="fake_add_to_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("success/<str:reference>/", views.order_success, name="order_success"),
]
