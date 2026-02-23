from rest_framework import viewsets
from payments.models import Payment, ProducerSettlement, SettlementLineItem
from api.serializers.payments import (
    PaymentSerializer,
    ProducerSettlementSerializer,
    SettlementLineItemSerializer,
)

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().order_by("-created_at")
    serializer_class = PaymentSerializer

class ProducerSettlementViewSet(viewsets.ModelViewSet):
    queryset = ProducerSettlement.objects.all().order_by("-settlement_week")
    serializer_class = ProducerSettlementSerializer

class SettlementLineItemViewSet(viewsets.ModelViewSet):
    queryset = SettlementLineItem.objects.all()
    serializer_class = SettlementLineItemSerializer