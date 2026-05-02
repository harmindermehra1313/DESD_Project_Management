"""
URL configuration for BRFN project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from admin_records import views as admin_views
from django.views.generic import TemplateView


    
handler400 = "BRFN.view.custom_400"
handler403 = "BRFN.view.custom_403"
handler404 = "BRFN.view.custom_404"
handler500 = "BRFN.view.custom_500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("home.urls", namespace="home")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("admin_records/", include("admin_records.urls", namespace="admin_records")),
    path("community/", include("community.urls", namespace="community")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path("orders/", include("orders.urls", namespace="orders")),
    path("payments/", include("payments.urls", namespace="payments")),
    path("products/", include("products.urls")),
    # path('producer/', include('products.urls')),
    path("reviews/", include("reviews.urls", namespace="reviews")),
    path("api/", include("api.urls", namespace="api")),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    # Cart Endpoint
    path("cart/", include(("carts.urls", "carts"), namespace="carts")),
    path("search/", admin_views.global_search, name="global_search"),
    # AI Recommendations Endpoint
    path("ai-recommendations/", include("ai_recommendations.urls")),
    path("cookie-policy/", TemplateView.as_view(template_name="cookie_policy.html"), name="cookie_policy"),
]
