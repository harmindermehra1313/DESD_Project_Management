# products/urls.py

from django.urls import path
from . import views
from .views.views_main import add_product, product_view, producer_products, edit_producer_product, cancel_producer_product, ProductDetailView, product_detail_page
from .views import reductions, api_reductions

urlpatterns = [
    # path('', views.product_list, name='products_list'),
    path('add/', add_product, name='add_product'),
    # path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path("<int:product_id>/", product_detail_page, name="product-detail"),  # /products/<pk>/
   
    # Harminder Edits
    path("category/<int:category_id>/", product_view, name="product_view"),
    path("producer/products/", producer_products, name="producer_products"),
    
    # Hannah edit: reductions handling
    path("reductions/", reductions.manage_reductions, name="producer_manage_reductions"),
    path("api/surplus/", api_reductions.SurplusListAPI.as_view(), name="api_surplus_list"),
    path("api/surplus/<int:pk>/create/", api_reductions.SurplusCreateAPI.as_view(), name="api_surplus_create"),
    path("api/surplus/<int:pk>/update/", api_reductions.SurplusUpdateAPI.as_view(), name="api_surplus_update"),
    path("api/surplus/<int:pk>/cancel/", api_reductions.SurplusCancelAPI.as_view(), name="api_surplus_cancel"),
    
    #Joe
    # path('producer/', producer_products, name='producer_products'),
    path('producer/products/<int:pk>/edit/', edit_producer_product, name='edit_producer_product'),
    path('producer/products/<int:pk>/cancel/', cancel_producer_product, name='cancel_producer_product'),
]