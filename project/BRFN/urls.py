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

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("home.urls")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("analytics/", include("analytics.urls", namespace="analytics")),
    path("community/", include("community.urls", namespace="community")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path('orders/', include("orders.urls", namespace="orders")),
    path('payments/', include('payments.urls', namespace="payments")),
    path('products/', include('products.urls', namespace='products')),
    path('reviews/', include('reviews.urls', namespace='reviews'))
]
