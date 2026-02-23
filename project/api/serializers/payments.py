from rest_framework import serializers
from payments.models import Payment, ProducerSettlement, SettlementLineItem
from api.serializers.orders import OrderSerializer, OrderItemSerializer
from api.serializers.accounts import ProducerSerializer

# Validation should happen here! TBC remove when added

class PaymentSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = "__all__"

class ProducerSettlementSerializer(serializers.ModelSerializer):
    producer = ProducerSerializer(read_only=True)

    class Meta:
        model = ProducerSettlement
        fields = "__all__"

class SettlementLineItemSerializer(serializers.ModelSerializer):
    settlement = ProducerSettlementSerializer(read_only=True)
    order_item = OrderItemSerializer(read_only=True)

    class Meta:
        model = SettlementLineItem
        fields = "__all__"