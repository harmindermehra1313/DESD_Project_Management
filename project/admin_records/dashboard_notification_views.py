from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from notifications.models import Notification


REVIEW_NOTIFICATION_TYPES = [
    Notification.Type.REVIEW_FLAGGED,
]


def get_notification_return_url(request):
    fallback_url = reverse("admin_records:index")

    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.headers.get("Referer")
        or fallback_url
    )

    if "/review-notifications/json/" in next_url:
        return fallback_url

    is_safe = url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )

    if not is_safe:
        return fallback_url

    return next_url


def get_review_notification_queryset(request, status=""):
    notifications = (
        Notification.objects
        .filter(
            user=request.user,
            type__in=REVIEW_NOTIFICATION_TYPES,
        )
        .select_related("user", "product", "order")
        .order_by("-created_at")
    )

    if status == "unread":
        notifications = notifications.filter(read_at__isnull=True)

    if status == "resolved":
        notifications = notifications.filter(resolved_at__isnull=False)

    if status == "unresolved":
        notifications = notifications.filter(resolved_at__isnull=True)

    return notifications


def get_review_notification_context(request):
    status = request.GET.get("status", "").strip()
    notification_type = request.GET.get("type", "").strip()

    page_number = (
        request.GET.get("page")
        or request.GET.get("notifications_page")
        or 1
    )

    review_notifications = get_review_notification_queryset(request, status=status)

    if notification_type:
        review_notifications = review_notifications.filter(type=notification_type)

    paginator = Paginator(review_notifications, 10)
    page_obj = paginator.get_page(page_number)

    base_review_notifications = Notification.objects.filter(
        user=request.user,
        type__in=REVIEW_NOTIFICATION_TYPES,
    )

    return {
        "page_obj": page_obj,
        "status": status,
        "notification_type": notification_type,
        "notification_return_url": get_notification_return_url(request),
        "total_notifications": base_review_notifications.count(),
        "unread_notifications": base_review_notifications.filter(
            read_at__isnull=True,
        ).count(),
        "unresolved_notifications": base_review_notifications.filter(
            resolved_at__isnull=True,
        ).count(),
        "flagged_review_notifications": base_review_notifications.filter(
            type=Notification.Type.REVIEW_FLAGGED,
            resolved_at__isnull=True,
        ).count(),
        "notification_type_choices": [
            choice
            for choice in Notification.Type.choices
            if choice[0] in REVIEW_NOTIFICATION_TYPES
        ],
    }


@staff_member_required
def admin_records_dashboard(request):
    context = get_review_notification_context(request)
    return render(request, "admin_records/index.html", context)


@staff_member_required
def review_notification_panel_json(request):
    context = get_review_notification_context(request)

    html = render_to_string(
        "admin_records/partials/review_notification_panel.html",
        context,
        request=request,
    )

    return JsonResponse(
        {
            "success": True,
            "html": html,
            "unread_count": context["unread_notifications"],
            "page": context["page_obj"].number,
        }
    )


@require_POST
@staff_member_required
def mark_review_notification_read(request, notification_id):
    notification = (
        Notification.objects
        .filter(
            id=notification_id,
            user=request.user,
            type__in=REVIEW_NOTIFICATION_TYPES,
        )
        .first()
    )

    if notification and notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
        messages.success(request, "Notification marked as read.")

    return redirect(get_notification_return_url(request))


@require_POST
@staff_member_required
def mark_all_review_notifications_read(request):
    updated_count = (
        Notification.objects
        .filter(
            user=request.user,
            type__in=REVIEW_NOTIFICATION_TYPES,
            read_at__isnull=True,
        )
        .update(read_at=timezone.now())
    )

    if updated_count:
        messages.success(
            request,
            f"{updated_count} notification{'s' if updated_count != 1 else ''} marked as read.",
        )
    else:
        messages.info(request, "No unread notifications found.")

    return redirect(get_notification_return_url(request))