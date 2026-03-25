from rest_framework import serializers
from notifications.models import (
    Notification,
    RecallNotice,
    RecallNotification,
    TraceabilityRecord,
)
from api.serializers.accounts import UserSerializer, ProducerSerializer, CustomerSerializer
from products.api.serializers.product_details import ProductInlineSerializer
from api.serializers.orders import OrderSerializer, OrderItemSerializer

# Validation should happen here! TBC remove when added

class NotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    product = ProductInlineSerializer(read_only=True)
    order = OrderSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = "__all__"

class RecallNoticeSerializer(serializers.ModelSerializer):
    producer = ProducerSerializer(read_only=True)
    product = ProductInlineSerializer(read_only=True)

    class Meta:
        model = RecallNotice
        fields = "__all__"

class RecallNotificationSerializer(serializers.ModelSerializer):
    recall = RecallNoticeSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    order = OrderSerializer(read_only=True)

    class Meta:
        model = RecallNotification
        fields = "__all__"

class TraceabilityRecordSerializer(serializers.ModelSerializer):
    order_item = OrderItemSerializer(read_only=True)
    product = ProductInlineSerializer(read_only=True)
    producer = ProducerSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)

    class Meta:
        model = TraceabilityRecord
        fields = "__all__"