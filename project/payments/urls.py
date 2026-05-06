from django.urls import path
from . import views
from .views import stripe_webhook

app_name = 'payments'

urlpatterns = [
    path("", views.index, name= 'index'),
    path("webhook/", stripe_webhook, name="stripe-webhook"),
]
