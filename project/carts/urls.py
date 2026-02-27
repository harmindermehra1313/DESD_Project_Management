from django.urls import path
from .views import CartPageView

app_name = "carts"

urlpatterns = [
    path("", CartPageView.as_view(), name="cart_page"),
]