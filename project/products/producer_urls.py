from django.urls import path
from . import views

urlpatterns = [
    path('products/', views.producer_products, name='producer_products'),
    path('products/<int:pk>/edit/', views.edit_producer_product, name='edit_producer_product'),
    path('products/<int:pk>/cancel/', views.cancel_producer_product, name='cancel_producer_product'),
]
