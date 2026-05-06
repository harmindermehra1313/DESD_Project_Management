from django.urls import path
from . import views, dashboard_notification_views

app_name = "admin_records"

urlpatterns = [
    path("", dashboard_notification_views.admin_records_dashboard, name="index"),
    path("", views.index, name="index"),
    path(
        "review-notifications/json/",
        dashboard_notification_views.review_notification_panel_json,
        name="review_notification_panel_json",
    ),
    path(
        "notifications/<int:notification_id>/read/",
        dashboard_notification_views.mark_review_notification_read,
        name="mark_admin_notification_read",
    ),
    path(
        "notifications/read-all/",
        dashboard_notification_views.mark_all_review_notifications_read,
        name="mark_all_admin_notifications_read",
    ),
    # Financial report
    path("financial-reports/", views.financial_reports, name="financial_reports"),
    path(
        "financial-reports/csv/",
        views.financial_reports_csv,
        name="financial_reports_csv",
    ),
    path(
        "financial-reports/pdf/",
        views.financial_reports_pdf,
        name="financial_report_pdf",
    ),
    # User and Producer list
    path("users/", views.user_list, name="user_list"),
    path("producers/", views.producer_list, name="producer_list"),
    path(
        "users/<int:user_id>/deactivate/", views.deactivate_user, name="deactivate_user"
    ),
    path(
        "users/<int:user_id>/reactivate/", views.reactivate_user, name="reactivate_user"
    ),
    # Search bar
    path("search/", views.global_search, name="global_search"),
    # Approval page
    path("approval-requests/", views.approval_requests, name="approval_request"),
    path(
        "products/<int:product_id>/approve/",
        views.approve_product,
        name="approve_product",
    ),
    path(
        "products/<int:product_id>/reject/", views.reject_product, name="reject_product"
    ),
    path(
        "api/product/<int:product_id>/", views.product_details, name="product_details"
    ),
    path(
        "action-required/<int:product_id>/",
        views.action_required,
        name="action_required",
    ),
]
