from django.urls import path

from reviews.views import ReviewCreateView

app_name = "reviews"

urlpatterns = [
    path("add/", ReviewCreateView.as_view(), name="add"),
]