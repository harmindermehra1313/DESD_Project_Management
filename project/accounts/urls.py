from django.urls import path
from . import views
from accounts.views import UnifiedRegistrationView

app_name = "accounts"

urlpatterns = [
     path("", views.register, name="register"),              # renders the form
     path("login/", views.login, name="login"),              # renders login
     path("api/register/", UnifiedRegistrationView.as_view(), name="api-register"),  # handles POST
]