from notifications.models import Notification

def unread_notification_count(request):
    if not request.user.is_authenticated:
        return {"unread_notifications": 0}

    count = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True
    ).count()

    return {"unread_notifications": count}
