from django.urls import path
from . import views

app_name = 'home'
urlpatterns = [
    path("", views.home, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("producer/", views.producer, name="producer"),
    path("producer/notifications/mark-read/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
]