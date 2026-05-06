from django.urls import path
from . import views

app_name = "community"

urlpatterns = [
    path("", views.community_hub, name="hub"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact_us, name="contact_us"),

    # Producer content dashboard
    path(
        "producer/content/",
        views.producer_content_dashboard,
        name="producer_content_dashboard",
    ),
    path(
        "producer/content/recipes/new/",
        views.recipe_create,
        name="recipe_create",
    ),
    path(
        "producer/content/stories/new/",
        views.farm_story_create,
        name="farm_story_create",
    ),

    # Public recipes and stories
    path("recipes/", views.recipe_list, name="recipe_list"),
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path(
        "recipes/<int:pk>/favourite/",
        views.toggle_recipe_favourite,
        name="toggle_recipe_favourite",
    ),
    path("stories/", views.story_list, name="story_list"),
    path("stories/<int:pk>/", views.story_detail, name="story_detail"),
    path(
        "producers/<int:producer_id>/",
        views.producer_profile,
        name="producer_profile",
    ),

    # Producer edit/delete
    path("recipes/<int:pk>/edit/", views.recipe_edit, name="recipe_edit"),
    path("recipes/<int:pk>/delete/", views.recipe_delete, name="recipe_delete"),
    path("stories/<int:pk>/edit/", views.farm_story_edit, name="farm_story_edit"),
    path("stories/<int:pk>/delete/", views.farm_story_delete, name="farm_story_delete"),

    # APIs
    path(
        "api/product/<int:product_id>/recipes/",
        views.api_product_recipes,
        name="api_product_recipes",
    ),
    path(
        "api/producer/content/",
        views.api_producer_content,
        name="api_producer_content",
    ),
    path(
        "api/producer/products/",
        views.api_producer_products,
        name="api_producer_products",
    ),
    path("api/recipe/<int:pk>/", views.recipe_api, name="recipe_api"),
    path("api/story/<int:pk>/", views.story_api, name="story_api"),
]