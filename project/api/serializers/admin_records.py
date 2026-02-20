from rest_framework import serializers
from admin_records.models import SecurityLog, AdminPost, ModerationLog, DistanceRecord
from accounts.models import Admin, Producer
from api.serializers.accounts import UserSerializer, AdminSerializer, ProducerSerializer

# Validation should happen here! TBC remove when added

class SecurityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityLog
        fields = "__all__"

class AdminPostSerializer(serializers.ModelSerializer):
    admin = AdminSerializer(read_only=True)

    class Meta:
        model = AdminPost
        fields = "__all__"

class ModerationLogSerializer(serializers.ModelSerializer):
    admin = AdminSerializer(read_only=True)
    producer = ProducerSerializer(read_only=True)

    class Meta:
        model = ModerationLog
        fields = "__all__"

class DistanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistanceRecord
        fields = "__all__"