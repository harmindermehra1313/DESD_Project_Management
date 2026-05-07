from django.urls import path
from . import views

app_name = "ai_admin"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("upload-model/", views.upload_model, name="upload_model"),
    path("activate/<int:model_id>/", views.activate_model, name="activate_model"),
]
