from django.urls import path
from . import views
from accounts.views import UnifiedRegistrationView

app_name = "accounts"

urlpatterns = [
    path("", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("api/register/", UnifiedRegistrationView.as_view(), name="api-register"),
    path("producer_dashboard/", views.producer_dashboard, name="producer_dashboard"),
    path("update-order-status/<int:summary_id>/", views.update_order_status, name="update_order_status"),
    path("profile/", views.profile, name="profile"),
]