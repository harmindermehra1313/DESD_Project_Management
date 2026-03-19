# products/urls.py

from django.urls import path
from . import views
from .views import product_detail_page

urlpatterns = [
    # path('', views.product_list, name='products_list'),
    path('add/', views.add_product, name='add_product'),
    # path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path("<int:product_id>/", product_detail_page, name="product-detail"),
    # Harminder Edits
    path("category/<int:category_id>/", views.product_view, name="product_view"),
    path("producer/products/", views.producer_products, name="producer_products"),
]