from rest_framework import viewsets
from admin_records.models import SecurityLog, AdminPost, ModerationLog, DistanceRecord
from api.serializers.admin_records import (
    SecurityLogSerializer,
    AdminPostSerializer,
    ModerationLogSerializer,
    DistanceRecordSerializer,
)

class SecurityLogViewSet(viewsets.ModelViewSet):
    queryset = SecurityLog.objects.all().order_by("-timestamp")
    serializer_class = SecurityLogSerializer

class AdminPostViewSet(viewsets.ModelViewSet):
    queryset = AdminPost.objects.all().order_by("-created_at")
    serializer_class = AdminPostSerializer

class ModerationLogViewSet(viewsets.ModelViewSet):
    queryset = ModerationLog.objects.all().order_by("-created_at")
    serializer_class = ModerationLogSerializer

class DistanceRecordViewSet(viewsets.ModelViewSet):
    queryset = DistanceRecord.objects.all().order_by("-calculated_at")
    serializer_class = DistanceRecordSerializer