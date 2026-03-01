# products/urls.py

from django.urls import path
from . import views
from .views import ProductListView, ProductDetailView

# These names match the {% url 'name' %} tags used in your HTML templates
urlpatterns = [
    # 1. Main Shop Page: yourwebsite.com/products/
    path('', views.product_list, name='products_list'),
    
    # 2. Add Product Page: yourwebsite.com/products/add/
    path('add/', views.add_product, name='add_product'),
    
    # 3. Product Detail Page: yourwebsite.com/products/1/
    path('<int:product_id>/', views.product_detail, name='product_detail'),
    
    # 4. Add to Cart Action: yourwebsite.com/products/cart/add/1/
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),

    path("", ProductListView.as_view(), name="list"),   # /products/
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),  # /products/<pk>/
]