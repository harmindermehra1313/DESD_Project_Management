# api/views/orders.py
from rest_framework import viewsets
from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
    RecurringOrder,
    RecurringOrderItem,
)
from api.serializers.orders import (
    OrderSerializer,
    OrderItemSerializer,
    ProducerOrderSummarySerializer,
    ProducerOrderStatusHistorySerializer,
    RecurringOrderSerializer,
    RecurringOrderItemSerializer,
)

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by("-order_date")
    serializer_class = OrderSerializer

class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

class ProducerOrderSummaryViewSet(viewsets.ModelViewSet):
    queryset = ProducerOrderSummary.objects.all().order_by("-delivery_date")
    serializer_class = ProducerOrderSummarySerializer

class ProducerOrderStatusHistoryViewSet(viewsets.ModelViewSet):
    queryset = ProducerOrderStatusHistory.objects.all().order_by("-changed_at")
    serializer_class = ProducerOrderStatusHistorySerializer

class RecurringOrderViewSet(viewsets.ModelViewSet):
    queryset = RecurringOrder.objects.all().order_by("-created_at")
    serializer_class = RecurringOrderSerializer

class RecurringOrderItemViewSet(viewsets.ModelViewSet):
    queryset = RecurringOrderItem.objects.all()
    serializer_class = RecurringOrderItemSerializer