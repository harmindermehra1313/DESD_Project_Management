from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    path("", views.index, name='index'),
    path("producer/content/", views.producer_content_dashboard, name="producer_content_dashboard"),
    path("contact/", views.contact_us, name='contact_us'),
    path("producer/content/recipes/new/", views.recipe_create, name="recipe_create"),
    path("producer/content/stories/new/", views.farm_story_create, name="farm_story_create"),

    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("producers/<int:producer_id>/", views.producer_profile, name="producer_profile"),
    path("api/product/<int:product_id>/recipes/", views.api_product_recipes, name="api_product_recipes"),
    path("api/producer/content/", views.api_producer_content, name="api_producer_content"),
    path("api/producer/products/", views.api_producer_products, name="api_producer_products"),
    path("api/recipes/create/", views.api_create_recipe, name="api_create_recipe"),
    path("api/stories/create/", views.api_create_story, name="api_create_story"),


    path("api/recipe/<int:pk>/", views.recipe_api, name="recipe_api"),
    path("api/story/<int:pk>/", views.story_api, name="story_api"),

    path("recipes/<int:pk>/edit/", views.recipe_edit, name="recipe_edit"),
    path("recipes/<int:pk>/delete/", views.recipe_delete, name="recipe_delete"),

    path("stories/<int:pk>/edit/", views.farm_story_edit, name="farm_story_edit"),
    path("stories/<int:pk>/delete/", views.farm_story_delete, name="farm_story_delete"),

    path("stories/<int:pk>/", views.story_detail, name="story_detail"),

<<<<<<< HEAD

    path("", views.index, name='index'),
    path("contact/", views.contact_us, name='contact_us'),
=======
    path("about/", views.about, name="about"),
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
]
