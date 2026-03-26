from django.urls import path
from .views import views_main
from accounts.views.views_main import UnifiedRegistrationView
from accounts.views.producer_payments import (
    producer_payments_view,
    download_payment_report_view,
    download_payment_csv_view,
    download_tax_year_pdf_view,
    download_tax_year_csv_view,
    download_tax_year_zip_view
)

app_name = "accounts"

urlpatterns = [
    path("", views_main.register, name="register"),
    path("login/", views_main.login_view, name="login"),
    path("logout/", views_main.logout_view, name="logout"),
    path("api/register/", UnifiedRegistrationView.as_view(), name="api-register"),
    path("auth/firebase/", views_main.firebase_auth_view),
    
    # Dashboard & Order Management
    path("producer_dashboard/", views_main.producer_dashboard, name="producer_dashboard"),
    path("update-order-status/<int:summary_id>/", views_main.update_order_status, name="update_order_status"),
    path("cancel-subscription/<int:sub_id>/", views_main.cancel_subscription, name="cancel_subscription"),
    
    path("profile/", views_main.profile, name="profile"),
    
    # Producer Payments
    path("producer/payments/", producer_payments_view, name="producer_payments"),
    path("producer/payments/report/<str:week_id>/", download_payment_report_view, name="download_payment_report"),
    path("producer/payments/csv/<str:week_id>/", download_payment_csv_view, name="download_payment_csv"),
    path("payments/tax-year/pdf/", download_tax_year_pdf_view, name="download_tax_year_pdf"),
    path("payments/tax-year/csv/", download_tax_year_csv_view, name="download_tax_year_csv"),
    path("payments/tax-year/zip/", download_tax_year_zip_view, name="download_tax_year_zip"),
]