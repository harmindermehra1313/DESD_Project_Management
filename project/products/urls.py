# products/urls.py

from django.urls import path
from . import views
from .views import ProductDetailView

urlpatterns = [
    path('', views.product_list, name='products_list'),
    path('add/', views.add_product, name='add_product'),
    # path('<int:product_id>/', views.product_detail, name='product_detail'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),  # /products/<pk>/
    # path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),  # /products/<pk>/
    # Harminder Edits
    path("category/<int:category_id>/", views.product_view, name="product_view"),
]