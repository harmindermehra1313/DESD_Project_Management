from django.urls import path
from . import views
from accounts.views import UnifiedRegistrationView

app_name = "accounts"

urlpatterns = [
     path("", views.register, name="register"),
     path("login/", views.login, name="login"),
     path("logout/", views.logout_view, name="logout"),
     path("api/register/", UnifiedRegistrationView.as_view(), name="api-register"),  # handles POST
     path("producer_dashboard/", views.producer_dashboard, name="producer_dashboard"),
]
