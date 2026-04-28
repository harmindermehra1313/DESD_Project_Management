# products/urls.py

from django.urls import path
from . import views
from .views.views_main import add_product, product_view, producer_products, edit_producer_product, cancel_producer_product, ProductDetailView, product_detail_page
from .views import reductions, api_reductions, batch
from community.views import api_product_recipes


app_name = 'products'

urlpatterns = [
    # path('', views.product_list, name='products_list'),
    path('add/', add_product, name='add_product'),
    path("<int:product_id>/", product_detail_page, name="product-detail"),  # /products/<pk>/
   
    # Harminder Edits
    path("category/<int:category_id>/", product_view, name="product_view"),
    path("producer/products/", producer_products, name="producer_products"),

    path("product/<int:product_id>/recipes/", api_product_recipes, name="product_recipes"),


    
    # Hannah edit: reductions handling
    path("reductions/", reductions.manage_reductions, name="producer_manage_reductions"),
    path("api/surplus/", api_reductions.SurplusListAPI.as_view(), name="api_surplus_list"),
    path("api/surplus/<int:pk>/create/", api_reductions.SurplusCreateAPI.as_view(), name="api_surplus_create"),
    path("api/surplus/<int:pk>/update/", api_reductions.SurplusUpdateAPI.as_view(), name="api_surplus_update"),
    path("api/surplus/<int:pk>/cancel/", api_reductions.SurplusCancelAPI.as_view(), name="api_surplus_cancel"),
    path("producer/products/<int:pk>/add-batch/",batch.add_batch,name="add_batch"),
    path("producer/products/<int:pk>/reduce-batch/",batch.reduce_batch,name="reduce_batch"),
    path("producer/products/<int:pk>/delete-batch/",batch.delete_batch,name="delete_batch"),

    #Joe
    # path('producer/', producer_products, name='producer_products'),
    path('producer/products/<int:pk>/edit/', edit_producer_product, name='edit_producer_product'),
    path('producer/products/<int:pk>/cancel/', cancel_producer_product, name='cancel_producer_product'),

]