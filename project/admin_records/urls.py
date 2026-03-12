from django.urls import path
from . import views

app_name = "admin_records"

urlpatterns = [
    path("", views.index, name="index"),
    path("financial-reports/", views.financial_reports, name="financial_reports"),
    path("financial-reports/csv/", views.financial_reports_csv, name="financial_reports_csv"),
    path("users/", views.user_list, name="user_list"),
    path("producers/", views.producer_list, name="producer_list"),

]

