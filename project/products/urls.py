# products/urls.py

from django.urls import path
from .views import ProductListView, ProductDetailView

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="list"),   # /products/
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),  # /products/<pk>/
]