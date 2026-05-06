from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

from .models import Notification


def index(request):
    return render(request, "notifications/index.html")


@login_required
@require_GET
def notification_panel_json(request):
    page_number = request.GET.get("page", 1)

    notifications_qs = (
        Notification.objects
        .filter(user=request.user)
        .select_related("order", "product")
        .order_by("-created_at")
    )

    paginator = Paginator(notifications_qs, 5)
    notifications = paginator.get_page(page_number)

    unread_count = notifications_qs.filter(read_at__isnull=True).count()

    html = render_to_string(
        "notifications/partials/profile_notification_panel.html",
        {
            "notifications": notifications,
            "unread_count": unread_count,
        },
        request=request,
    )

    return JsonResponse({
        "success": True,
        "html": html,
        "unread_count": unread_count,
        "page": notifications.number,
    })
    
@login_required
@require_GET
def producer_notification_panel_json(request):
    page_number = request.GET.get("page", 1)

    notifications_qs = (
        Notification.objects
        .filter(user=request.user)
        .select_related("order", "product")
        .order_by("-created_at")
    )

    paginator = Paginator(notifications_qs, 5)
    notifications = paginator.get_page(page_number)

    unread_count = notifications_qs.filter(read_at__isnull=True).count()

    html = render_to_string(
        "notifications/partials/producer_notification_panel.html",
        {
            "notifications": notifications,
            "unread_count": unread_count,
        },
        request=request,
    )

    return JsonResponse({
        "success": True,
        "html": html,
        "unread_count": unread_count,
        "page": notifications.number,
    })