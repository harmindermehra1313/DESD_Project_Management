# api/views/orders.py
from rest_framework import viewsets
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status 
from django.db import transaction
from orders.models import (
    Order,
    OrderItem,
    ProducerOrderSummary,
    ProducerOrderStatusHistory,
    RecurringOrder,
    RecurringOrderItem
)
from api.serializers.orders import (
    OrderSerializer,
    OrderItemSerializer,
    ProducerOrderSummarySerializer,
    ProducerOrderStatusHistorySerializer,
    RecurringOrderSerializer,
    RecurringOrderItemSerializer,
    CheckoutSerializer
)
from django.apps import apps
from time import timezone
from datetime import timedelta

Product = apps.get_model('products', 'Product')
Payment = apps.get_model('payments', 'Payment')

User = apps.get_model('accounts', 'User') # TBC remove!

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

class CheckoutAPIView(APIView):
    def post(self, request):
        # TBC - set user as customer from seeder
        request.user = User.objects.get(email="mark42@hotmail.com")

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = request.session.get("cart", {})
        items = cart.get("items", [])

        if not items:
            return Response(
                {"error": "Cart is empty"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        delivery_method = serializer.validated_data["delivery_or_collection"]
        delivery_date = serializer.validated_data["delivery_date"]
        payment_method = serializer.validated_data["payment_method"]
        special_instructions = serializer.validated_data.get("special_instructions", "")

        with transaction.atomic():
            # Create order
            order = Order.objects.create(
                user=request.user,
                delivery_address=request.user.addresses.first(), # TBC fix address so not just first!
                delivery_or_collection=delivery_method,
                delivery_date=delivery_date,
                status=Order.Status.PENDING,
            )

            # Create order items
            total_amount = 0
            for entry in items:
                product = Product.objects.get(id=entry["product_id"])
                quantity = entry["quantity"]
                line_total = product.price * quantity
                total_amount += line_total

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    producer=product.producer,
                    quantity=quantity,
                    original_unit_price=product.price,
                    final_unit_price=product.price,
                    commission_amount=0,
                    discount_amount=0,
                    total_price=line_total,
                    preparation_deadline=timezone.now() + timedelta(hours=48)
                )
            
            # Update order totals
            order.total_price = total_amount
            order.final_total_price = total_amount
            order.save()

            # Create payment record
            Payment.objects.create(
                order=order,
                amount=total_amount,
                payment_method=serializer.validated_data["payment_method"],
                payment_status=Payment.Status.PENDING,
                sandbox_mode=True,
            )

            # Clear cart
            request.session["cart"] = {"items": []}

        return Response(
            {
                "order_id": order.id,
                "unique_reference": order.unique_reference
            },
            status=status.HTTP_201_CREATED)