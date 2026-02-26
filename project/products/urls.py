from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    path("", views.products_page, name="list"),
    path("<int:pk>/", views.ProductDetailPage.as_view(), name="detail"),
]