from rest_framework import serializers

from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
    RecurringOrder,
    RecurringOrderItem,
)
from api.serializers.accounts import UserSerializer, ProducerSerializer
from api.serializers.accounts import AddressSerializer
from products.api.serializers.product_details import ProductInlineSerializer
from products.api.serializers.product_details import InventorySerializer

# Validation should happen here! TBC remove when added

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductInlineSerializer(read_only=True)
    producer = ProducerSerializer(read_only=True)
    inventory = InventorySerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    delivery_address = AddressSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = "__all__"

class ProducerOrderSummarySerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    producer = ProducerSerializer(read_only=True)

    class Meta:
        model = ProducerOrderSummary
        fields = "__all__"

class ProducerOrderStatusHistorySerializer(serializers.ModelSerializer):
    producer_order_summary = ProducerOrderSummarySerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)

    class Meta:
        model = ProducerOrderStatusHistory
        fields = "__all__"

class RecurringOrderItemSerializer(serializers.ModelSerializer):
    product = ProductInlineSerializer(read_only=True)

    class Meta:
        model = RecurringOrderItem
        fields = "__all__"

class RecurringOrderSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    delivery_address = AddressSerializer(read_only=True)
    items = RecurringOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = RecurringOrder
        fields = "__all__"
