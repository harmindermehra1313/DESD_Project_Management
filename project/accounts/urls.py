from django.urls import path
from .views import views_main
from .views import profile_views
from accounts.views.views_main import UnifiedRegistrationView
from accounts.views.views_main import UnifiedRegistrationView, check_email_exists
from accounts.views import profile_views, producer_stripe
from accounts.views.producer_payments import (
    producer_payments_view,
    download_payment_report_view,
    download_payment_csv_view,
    download_tax_year_pdf_view,
    download_tax_year_csv_view,
    download_tax_year_zip_view,
)

app_name = "accounts"

urlpatterns = [
    path("", views_main.register, name="register"),
    path("login/", views_main.login_view, name="login"),
    path("logout/", views_main.logout_view, name="logout"),
    path("api/register/", UnifiedRegistrationView.as_view(), name="api-register"),
    path("auth/firebase/", views_main.firebase_auth_view),
    path("auth/check-email/", check_email_exists, name="check_email"),
    # Dashboard & Order Management
    path(
        "producer_dashboard/", views_main.producer_dashboard, name="producer_dashboard"
    ),
    path(
        "update-order-status/<int:summary_id>/",
        views_main.update_order_status,
        name="update_order_status",
    ),
    path(
        "cancel-subscription/<int:sub_id>/",
        views_main.cancel_subscription,
        name="cancel_subscription",
    ),
    path(
        "toggle-subscription/<int:sub_id>/",
        views_main.toggle_subscription,
        name="toggle_subscription",
    ),
    path("profile/", profile_views.profile, name="profile"),
    path(
        "profile/notifications/<int:pk>/read/",
        profile_views.customer_mark_notification_read,
        name="customer_mark_notification_read",
    ),
    path(
        "profile/notifications/read-all/",
        profile_views.customer_mark_all_notifications_read,
        name="customer_mark_all_notifications_read",
    ),
    path(
        "cancel-producer-order/<int:summary_id>/",
        views_main.cancel_producer_order,
        name="cancel_producer_order",
    ),
    path(
        "cancel-producer-order-item/<int:item_id>/",
        views_main.cancel_producer_order_item,
        name="cancel_producer_order_item",
    ),
    # Producer Payments
    path("producer/payments/", producer_payments_view, name="producer_payments"),
    path(
        "producer/payments/report/<str:week_id>/",
        download_payment_report_view,
        name="download_payment_report",
    ),
    path(
        "producer/payments/csv/<str:week_id>/",
        download_payment_csv_view,
        name="download_payment_csv",
    ),
    path(
        "payments/tax-year/pdf/",
        download_tax_year_pdf_view,
        name="download_tax_year_pdf",
    ),
    path(
        "payments/tax-year/csv/",
        download_tax_year_csv_view,
        name="download_tax_year_csv",
    ),
    path(
        "payments/tax-year/zip/",
        download_tax_year_zip_view,
        name="download_tax_year_zip",
    ),
    # Producer Stripe Connect
    path(
        "producer/stripe/connect/",
        producer_stripe.connect_stripe_account,
        name="producer_stripe_connect",
    ),
    path(
        "producer/stripe/refresh/",
        producer_stripe.onboarding_refresh,
        name="producer_stripe_onboarding_refresh",
    ),
    path(
        "producer/stripe/dashboard/",
        producer_stripe.stripe_dashboard,
        name="producer_stripe_dashboard",
    ),
    path(
        "producer/stripe/update-method/",
        producer_stripe.update_payout_method,
        name="update_payout_method",
    ),
    # Producer manual payout settings
    path(
        "producer/settings/",
        producer_stripe.producer_settings,
        name="producer_settings",
    ),
    path(
        "api/producer/update-payout/",
        producer_stripe.update_payout_api,
        name="update_payout_api",
    ),
]
