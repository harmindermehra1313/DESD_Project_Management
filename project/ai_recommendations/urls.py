from django.urls import path

from . import views

app_name = "ai_recommendations"

urlpatterns = [
    path(
        "track/",
        views.track_interaction,
        name="track_interaction",
    ),
    path(
        "products/<int:product_id>/",
        views.product_recommendations_api,
        name="product_recommendations_api",
    ),
]