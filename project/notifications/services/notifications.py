from notifications.models import Notification
from django.utils import timezone

class NotificationService:

    @staticmethod
    def create_unique(user, type, message, product=None, order=None):
        """
        Creates a notification only if an unresolved one doesn't already exist.
        """

        existing = Notification.objects.filter(
            user=user,
            type=type,
            product=product,
            order=order,
            resolved_at__isnull=True
        ).first()

        if existing:
            return existing # Do not duplicate

        return Notification.objects.create(
            user=user,
            type=type,
            message=message,
            product=product,
            order=order
        )

    @staticmethod
    def resolve_for_product(product, type):
        Notification.objects.filter(
            product=product,
            type=type,
            resolved_at__isnull=True
        ).update(resolved_at=timezone.now())
    
    @staticmethod
    def mark_read(notification):
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
    
    @staticmethod
    def mark_all_read(user):
        Notification.objects.filter(
            user=user,
            read_at__isnull=True
        ).update(read_at=timezone.now())

