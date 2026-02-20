from rest_framework import viewsets
from notifications.models import (
    Notification,
    RecallNotice,
    RecallNotification,
    TraceabilityRecord,
)
from api.serializers.notifications import (
    NotificationSerializer,
    RecallNoticeSerializer,
    RecallNotificationSerializer,
    TraceabilityRecordSerializer,
)

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all().order_by("-created_at")
    serializer_class = NotificationSerializer

class RecallNoticeViewSet(viewsets.ModelViewSet):
    queryset = RecallNotice.objects.all().order_by("-issued_at")
    serializer_class = RecallNoticeSerializer

class RecallNotificationViewSet(viewsets.ModelViewSet):
    queryset = RecallNotification.objects.all().order_by("-notified_at")
    serializer_class = RecallNotificationSerializer

class TraceabilityRecordViewSet(viewsets.ModelViewSet):
    queryset = TraceabilityRecord.objects.all().order_by("-timestamp")
    serializer_class = TraceabilityRecordSerializer