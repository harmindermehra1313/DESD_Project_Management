from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/panel/", views.notification_panel_json, name="notification_panel_json"),
]